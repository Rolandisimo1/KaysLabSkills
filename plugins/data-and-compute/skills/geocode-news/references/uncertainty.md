# Uncertainty: the point-radius model and Darwin Core output

## The model

Every georeference is a **circle**: a center point (`decimalLatitude`,
`decimalLongitude`) and a **radius** (`coordinateUncertaintyInMeters`) equal to
the largest plausible distance from that center to where the true location could
be (Wieczorek et al. 2004; GBIF Best Practices, Chapman & Wieczorek 2020). The
radius is the whole point of the method: it is what lets a downstream analysis
weight, filter, or buffer a location honestly. A coordinate without a radius is
not a georeference.

Uncertainty is never 0 and never null. Even a coordinate copied verbatim from a
source carries that source's measurement error.

## Where the radius comes from, in priority order

### 1. Gazetteer bounding box (preferred)

If the geocoder returns an extent (Nominatim `boundingbox`, GeoNames `bbox`),
compute the radius as the great-circle distance from the center to a corner —
i.e. half the diagonal of the box. This is derived from the actual feature, so it
is the most defensible value and it naturally scales: a country's box gives a
country-sized radius, a building's box gives a building-sized one.

```
radius_m = haversine(center_lat, center_lon, corner_lat, corner_lon)
```

Use the farther of the two corners if the box is not centered on the returned
point. `geocode.py` implements this as `radius_from_bbox()`.

### 2. Feature-type defaults (no bbox available)

When only a point comes back, fall back to a typed default. These are
order-of-magnitude starting points in the museum tradition — adjust to your
corpus, and prefer a real bbox whenever you can get one.

| Feature type                                   | Default radius |
|------------------------------------------------|----------------|
| Precise address / building / named facility    | 100 m          |
| Street / intersection / small POI              | 300 m          |
| Village / small town / neighborhood            | 2 km           |
| Small city                                     | 5 km           |
| Large city / metro                              | 15–30 km       |
| County / district (second-level admin)          | 30–75 km       |
| State / province (first-level admin)            | 100–300 km     |
| Small country                                   | 100–300 km     |
| Large country                                   | 500–1000+ km   |
| Named region without fixed bounds ("the Sahel")| use a bounding polygon's radius, or flag as very coarse |
| Water body (named lake/bay/strait)             | extent-based; radius from its bbox |

These echo the museum convention (e.g. a Grand-Canyon-scale locality on the order
of a few km, a city like Phoenix on the order of tens of km).

### 3. Relative offsets — "distance at a heading"

For "D km <bearing> of <anchor>" (a museum "distance at a heading" locality):

1. Resolve and geocode the **anchor**; get its center and its radius `r_anchor`.
2. Compute the offset center by moving distance `D` along the bearing from the
   anchor (`offset_point()` in `geocode.py`, a standard destination-point
   formula on a sphere).
3. Combine uncertainties into the new radius:

```
radius = r_anchor              # the anchor could be anywhere in its own circle
       + distance_imprecision  # e.g. "20 km" is ±? -> ~half the rounding step
       + heading_imprecision   # arc error: D * angular_uncertainty_in_radians
```

A vague bearing ("north of") carries a large heading imprecision; a precise one
("bearing 210°") carries little. For "near X" / "outskirts of X" with no
distance, treat it as the anchor's radius plus roughly the anchor's own extent
(the true point is somewhere around the edge of X). Combining terms additively is
the conservative museum choice; use the Georeferencing Calculator's combination
rules if you need the rigorous version.

## Related but distinct: coordinatePrecision

`coordinateUncertaintyInMeters` is the *total* horizontal uncertainty.
`coordinatePrecision` records only the *rounding* precision of the stored lat/lon
(e.g. 0.01 degrees). They are different fields; don't conflate them. Precision is
a component of uncertainty, not a substitute for it.

## Darwin Core output fields

Emit these per location so the result is interoperable with GBIF-style tooling
and self-documenting. (`dwc:` prefix optional.)

Core geometry:
- `decimalLatitude`, `decimalLongitude` — center, decimal degrees, WGS84,
  **south and west negative**.
- `geodeticDatum` — datum/CRS. Web gazetteers are WGS84 / EPSG:4326. Always set.
- `coordinateUncertaintyInMeters` — the radius. Positive, never 0.
- `coordinatePrecision` — optional; rounding precision of the coordinates.

Provenance and verbatim:
- `verbatimLocality` — the exact mention string from the text.
- `locality` — the resolved unambiguous reference string.
- `higherGeography` / `country` / `countryCode` / `stateProvince` / `county` /
  `municipality` — filled from the resolved hierarchy where known.
- `georeferenceSources` — the gazetteer(s) used (e.g. "Nominatim/OSM").
- `georeferenceProtocol` — e.g. "point-radius method; Chapman & Wieczorek 2020".
- `georeferencedBy` / `georeferencedDate` — who/what ran it and when.
- `georeferenceRemarks` — disambiguation reasoning, any fallback/coarsening,
  cross-geocoder agreement, and the relevance role.

Suggested extension columns for news:
- `featureType` — the type used for defaults.
- `relevanceRole` — `event` / `dateline` / `incidental`.
- `resolutionConfidence` — model-reported or heuristic confidence in the *name*
  resolution (distinct from spatial uncertainty).
- `verbatimContext` — the sentence the mention came from.

## A worked example

Text: *"Fighting continued around Goma, and aid was staged 20 km north of the
city."*

Two records:
1. `verbatimLocality` = "Goma"; `locality` = "Goma, North Kivu, Democratic
   Republic of the Congo"; `featureType` = large city; center from gazetteer;
   `coordinateUncertaintyInMeters` from its bbox (~7–10 km); `relevanceRole` =
   event.
2. `verbatimLocality` = "20 km north of the city"; anchor = Goma; center =
   `offset_point(Goma, 20 km, bearing 0°)`; radius = Goma's radius + a small
   distance imprecision + heading imprecision for "north" (roughly 45° of arc);
   `relevanceRole` = event; remarks note the offset computation.
