"""
geocode.py — reference implementation of stages 3-5 of the news-geocoding
pipeline: gazetteer lookup, point-radius uncertainty, and Darwin Core output.

Design contract:
  * Coordinates come ONLY from a gazetteer (or are computed from a gazetteered
    anchor for relative offsets). Never from a language model.
  * Every returned record carries a positive coordinateUncertaintyInMeters.
  * Failures return an explicit unresolved record, never a fabricated point.

This is intentionally geocoder-agnostic and dependency-light. The default
backend is Nominatim/OSM (public server: 1 req/s, needs a real User-Agent).
Swap in GeoNames/ArcGIS/Pelias by implementing the same tiny interface.

Stages 1-2 (recognize + resolve with an LLM) are upstream; this module consumes
their output: a list of resolved mentions, each with a reference_string,
feature_type, relevance_role, and optional offset. See references/ for those.
"""

from __future__ import annotations

import json
import math
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict, field
from typing import Optional

# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

_EARTH_R = 6_371_008.8  # mean Earth radius, meters


def haversine_m(lat1, lon1, lat2, lon2):
    """Great-circle distance in meters."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_R * math.asin(min(1.0, math.sqrt(a)))


def offset_point(lat, lon, distance_m, bearing_deg):
    """Destination point given start, distance (m), and bearing (deg from N).

    Standard spherical destination-point formula. Used for relative localities
    like '20 km north of X': geocode X, then offset.
    """
    d = distance_m / _EARTH_R
    brg = math.radians(bearing_deg)
    p1 = math.radians(lat)
    l1 = math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(brg))
    l2 = l1 + math.atan2(
        math.sin(brg) * math.sin(d) * math.cos(p1),
        math.cos(d) - math.sin(p1) * math.sin(p2),
    )
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def radius_from_bbox(center_lat, center_lon, south, north, west, east):
    """Point-radius from a gazetteer bounding box: farthest corner distance."""
    corners = [(south, west), (south, east), (north, west), (north, east)]
    return max(haversine_m(center_lat, center_lon, la, lo) for la, lo in corners)


# --------------------------------------------------------------------------
# Feature-type default radii (meters). Fallbacks only; a real bbox wins.
# See references/uncertainty.md for the reasoning.
# --------------------------------------------------------------------------

DEFAULT_RADIUS_M = {
    "address": 100,
    "poi": 300,
    "street": 300,
    "village": 2_000,
    "town": 2_000,
    "city": 20_000,
    "county": 50_000,
    "state_province": 200_000,
    "country": 700_000,
    "water_body": 20_000,
    "natural_feature": 10_000,
    "region": 300_000,
    "relative_offset": 5_000,  # only used if anchor radius is somehow unavailable
}
_UNKNOWN_TYPE_RADIUS_M = 30_000


# --------------------------------------------------------------------------
# Output record (Darwin Core-flavored)
# --------------------------------------------------------------------------

@dataclass
class GeoRecord:
    verbatimLocality: str
    locality: Optional[str] = None            # resolved reference string
    decimalLatitude: Optional[float] = None
    decimalLongitude: Optional[float] = None
    geodeticDatum: str = "WGS84"
    coordinateUncertaintyInMeters: Optional[float] = None
    country: Optional[str] = None
    stateProvince: Optional[str] = None
    featureType: Optional[str] = None          # extension
    relevanceRole: Optional[str] = None        # extension: event/dateline/incidental
    resolutionConfidence: Optional[float] = None
    georeferenceSources: Optional[str] = None
    georeferenceProtocol: str = "point-radius method; Chapman & Wieczorek 2020"
    georeferenceRemarks: str = ""
    resolved: bool = False

    def to_dict(self):
        return asdict(self)


# --------------------------------------------------------------------------
# Gazetteer backend (Nominatim reference implementation)
# --------------------------------------------------------------------------

class NominatimBackend:
    """Minimal Nominatim client. Respect the public server's 1 req/s limit,
    or point base_url at your self-hosted instance for batch work."""

    name = "Nominatim/OSM"

    def __init__(self, user_agent, base_url="https://nominatim.openstreetmap.org",
                 min_interval_s=1.0):
        if not user_agent or "example" in user_agent.lower():
            raise ValueError("Set a real, contactable User-Agent for Nominatim.")
        self.user_agent = user_agent
        self.base_url = base_url.rstrip("/")
        self.min_interval_s = min_interval_s
        self._last = 0.0

    def _throttle(self):
        wait = self.min_interval_s - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def search(self, reference_string):
        """Return a normalized dict or None. Never returns invented data."""
        self._throttle()
        q = urllib.parse.urlencode({
            "q": reference_string, "format": "jsonv2", "limit": 1,
            "addressdetails": 1,
        })
        url = f"{self.base_url}/search?{q}"
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        if not data:
            return None
        top = data[0]
        lat, lon = float(top["lat"]), float(top["lon"])
        bbox = None
        if top.get("boundingbox"):
            s, n, w, e = (float(x) for x in top["boundingbox"])
            bbox = (s, n, w, e)
        addr = top.get("address", {})
        return {
            "lat": lat, "lon": lon, "bbox": bbox,
            "matched_name": top.get("display_name"),
            "osm_type": top.get("type"),
            "country": addr.get("country"),
            "state": addr.get("state"),
        }


# --------------------------------------------------------------------------
# On-disk cache: a corpus re-run should hit the network zero times for repeats
# --------------------------------------------------------------------------

class JsonCache:
    def __init__(self, path="geocode_cache.json"):
        self.path = path
        self._d = {}
        if os.path.exists(path):
            with open(path) as f:
                self._d = json.load(f)

    def get(self, key):
        return self._d.get(key)

    def put(self, key, value):
        self._d[key] = value
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._d, f)
        os.replace(tmp, self.path)


# --------------------------------------------------------------------------
# Core: resolve one already-LLM-resolved mention to a point-radius record
# --------------------------------------------------------------------------

def _assign_radius(rec: GeoRecord, hit: dict):
    """Priority: gazetteer bbox -> feature-type default -> unknown default."""
    if hit.get("bbox"):
        s, n, w, e = hit["bbox"]
        r = radius_from_bbox(hit["lat"], hit["lon"], s, n, w, e)
        rec.coordinateUncertaintyInMeters = max(round(r), 30)  # floor: never ~0
        rec.georeferenceRemarks += " Radius from gazetteer bounding box."
    else:
        r = DEFAULT_RADIUS_M.get(rec.featureType, _UNKNOWN_TYPE_RADIUS_M)
        rec.coordinateUncertaintyInMeters = r
        rec.georeferenceRemarks += f" Radius from feature-type default ({rec.featureType})."


def geocode_mention(mention: dict, backend, cache: Optional[JsonCache] = None) -> GeoRecord:
    """
    `mention` is the output of the LLM resolution stage, e.g.:
      {
        "verbatim": "20 km north of the city",
        "reference_string": "Goma, North Kivu, Democratic Republic of the Congo",
        "feature_type": "relative_offset",
        "relevance_role": "event",
        "offset": {"anchor": "...", "distance_km": 20, "bearing_deg": 0,
                   "fuzziness": "cardinal"},
        "disambiguation": "...",
        "resolution_confidence": 0.9
      }
    """
    rec = GeoRecord(
        verbatimLocality=mention.get("verbatim", ""),
        locality=mention.get("reference_string"),
        featureType=mention.get("feature_type"),
        relevanceRole=mention.get("relevance_role"),
        resolutionConfidence=mention.get("resolution_confidence"),
        georeferenceSources=backend.name,
        georeferenceRemarks=mention.get("disambiguation", "").strip(),
    )

    ref = mention.get("reference_string")
    if not ref:
        rec.georeferenceRemarks += " UNRESOLVED: no reference string from resolver."
        return rec

    # Look up (with cache). The reference string is the anchor for offsets.
    cache_key = f"{backend.name}::{ref}"
    hit = cache.get(cache_key) if cache else None
    if hit is None:
        try:
            hit = backend.search(ref)
        except Exception as exc:  # network/parse failure -> unresolved, not a guess
            rec.georeferenceRemarks += f" UNRESOLVED: lookup error ({exc})."
            return rec
        if cache:
            cache.put(cache_key, hit)

    if not hit:
        rec.georeferenceRemarks += " UNRESOLVED: no gazetteer match."
        return rec

    rec.country = hit.get("country")
    rec.stateProvince = hit.get("state")

    offset = mention.get("offset")
    if mention.get("feature_type") == "relative_offset" and offset:
        # Anchor center + radius, then apply the offset.
        anchor_lat, anchor_lon = hit["lat"], hit["lon"]
        if hit.get("bbox"):
            s, n, w, e = hit["bbox"]
            anchor_r = radius_from_bbox(anchor_lat, anchor_lon, s, n, w, e)
        else:
            anchor_r = DEFAULT_RADIUS_M.get("city", 20_000)

        dist_km = offset.get("distance_km")
        bearing = offset.get("bearing_deg")
        if dist_km is not None and bearing is not None:
            dist_m = dist_km * 1000.0
            rec.decimalLatitude, rec.decimalLongitude = offset_point(
                anchor_lat, anchor_lon, dist_m, bearing)
            # Combine uncertainties (conservative additive form).
            dist_imprecision = _distance_imprecision_m(dist_km)
            heading_imprecision = dist_m * _heading_uncertainty_rad(offset.get("fuzziness"))
            rec.coordinateUncertaintyInMeters = round(
                anchor_r + dist_imprecision + heading_imprecision)
            rec.georeferenceRemarks += (
                f" Computed offset {dist_km} km @ {bearing} deg from anchor; "
                f"radius = anchor({round(anchor_r)}) + dist({round(dist_imprecision)}) "
                f"+ heading({round(heading_imprecision)}) m.")
        else:
            # "near"/"outskirts": center on anchor, widen by ~its own extent.
            rec.decimalLatitude, rec.decimalLongitude = anchor_lat, anchor_lon
            rec.coordinateUncertaintyInMeters = round(anchor_r * 2)
            rec.georeferenceRemarks += " Fuzzy 'near' offset: anchor center, doubled radius."
        rec.resolved = True
        return rec

    # Ordinary named place.
    rec.decimalLatitude, rec.decimalLongitude = hit["lat"], hit["lon"]
    _assign_radius(rec, hit)
    rec.resolved = True
    return rec


def _distance_imprecision_m(dist_km):
    """Rounding imprecision of a stated distance. '20 km' -> tens digit -> ~5 km;
    '5 km' -> ones -> ~0.5 km. Half the apparent rounding step."""
    if dist_km <= 0:
        return 0.0
    step = 10 ** math.floor(math.log10(dist_km))
    return (step / 2.0) * 1000.0


def _heading_uncertainty_rad(fuzziness):
    """Angular uncertainty of a bearing description, in radians.
    Precise bearing ~ +/-5 deg; cardinal ('north') ~ +/-22.5 deg; vague more."""
    table = {
        "precise": math.radians(5),
        "intercardinal": math.radians(22.5),
        "cardinal": math.radians(22.5),
        "vague": math.radians(45),
    }
    return table.get(fuzziness, math.radians(30))


# --------------------------------------------------------------------------
# Batch entry point
# --------------------------------------------------------------------------

def geocode_mentions(mentions, backend, cache_path="geocode_cache.json"):
    cache = JsonCache(cache_path)
    return [geocode_mention(m, backend, cache).to_dict() for m in mentions]


if __name__ == "__main__":
    # Tiny self-test of the geometry, no network needed.
    # Berlin bbox sanity + a 20 km north offset.
    berlin = (52.52, 13.405)
    d = haversine_m(*berlin, *offset_point(*berlin, 20_000, 0))
    assert abs(d - 20_000) < 5, d
    r = radius_from_bbox(52.52, 13.405, 52.34, 52.68, 13.09, 13.76)
    print(f"offset check ok ({d:.1f} m); Berlin-ish bbox radius ~ {r/1000:.1f} km")
