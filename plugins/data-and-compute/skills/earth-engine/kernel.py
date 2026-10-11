# kernel.py — general Google Earth Engine extraction helpers.
# Loaded by skill("earth-engine"). Third-party imports (ee, pyproj) are
# deferred into function bodies so the skill loads before they're installed.

# ---- Worked-example reference: MapBiomas Brazil (Collection 10 / 3-beta 10m) ----
# Verified live against EE; each carries a classification_2024 band. These are
# ONE example dataset — the extract_* helpers work with any ee.Image.
MAPBIOMAS_ASSETS = {
    "lulc_10m": "projects/mapbiomas-public/assets/brazil/lulc_10m/collection3/mapbiomas_10m_collection3_integration_v1",
    "lulc_30m": "projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_coverage_v2",
    "agriculture_cycles": "projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_agriculture_number_cycles_v2",
}
MAPBIOMAS_LEGEND = {
    1: "Forest", 3: "Forest Formation", 4: "Savanna Formation", 5: "Mangrove",
    6: "Floodable Forest", 49: "Wooded Sandbank Veg", 10: "Herbaceous/Shrubby",
    11: "Wetland", 12: "Grassland", 32: "Hypersaline Tidal Flat", 29: "Rocky Outcrop",
    50: "Herbaceous Sandbank Veg", 13: "Other Non-Forest Nat.", 14: "Farming",
    15: "Pasture", 18: "Agriculture", 19: "Temporary Crop", 39: "Soybean",
    20: "Sugar Cane", 40: "Rice", 62: "Cotton", 41: "Other Temp Crop",
    36: "Perennial Crop", 46: "Coffee", 47: "Citrus", 35: "Palm Oil",
    48: "Other Perennial Crop", 9: "Forest Plantation", 21: "Mosaic Agri/Pasture",
    22: "Non-veg Area", 23: "Beach/Dune/Sand", 24: "Urban", 30: "Mining",
    25: "Other Non-veg", 26: "Water", 33: "River/Lake/Ocean", 31: "Aquaculture",
    27: "Not Observed", 0: "Unknown",
}
MAPBIOMAS_ECO_GROUPS = {
    "forest":       [1, 3, 5, 6, 49],
    "savanna":      [4],
    "open_natural": [10, 11, 12, 13, 29, 32, 50],
    "agriculture":  [9, 14, 15, 18, 19, 20, 21, 35, 36, 39, 40, 41, 46, 47, 48, 62],
    "urban_other":  [22, 23, 24, 25, 26, 30, 31, 33],
}
MAPBIOMAS_NATIVE_CODES = [1, 3, 4, 5, 6, 49, 10, 11, 12, 32, 29, 50, 13]


# ------------------------------- Auth --------------------------------------
def gee_init(key_path, service_account=None, project=None):
    """Initialize Earth Engine with a service-account JSON key (headless/sandbox).
    Reads client_email + project_id from the key if not given. The SA needs
    Earth Engine Resource *Writer* (compute) + Service Usage Consumer on the
    project. Requires oauth2.googleapis.com + earthengine.googleapis.com."""
    import ee, json
    meta = json.load(open(key_path))
    sa = service_account or meta["client_email"]
    proj = project or meta["project_id"]
    ee.Initialize(ee.ServiceAccountCredentials(sa, key_path), project=proj)
    return {"service_account": sa, "project": proj, "check": ee.Number(1).add(1).getInfo()}


def check_asset(asset_id, kind="image", band=None):
    """Verify an asset exists and (optionally) that a band is present.
    kind: 'image' or 'image_collection'. Returns {'bands', 'has_band'}."""
    import ee
    obj = ee.Image(asset_id) if kind == "image" else ee.ImageCollection(asset_id).first()
    bands = obj.bandNames().getInfo()
    return {"bands": bands, "has_band": (band in bands) if band else None}


# ------------------------- Point / spatial layout --------------------------
def point_spacing(df, group_col=None, lon_col="longitude", lat_col="latitude"):
    """Nearest-neighbor spacing (m), overall and (optionally) within groups.
    Use to pick buffer radii: a buffer whose diameter exceeds typical NN
    spacing overlaps neighbors and becomes spatially autocorrelated.
    Returns (per_group_df_or_None, overall_dict)."""
    import numpy as np, pandas as pd
    from pyproj import Geod
    geod = Geod(ellps="WGS84")
    def nn(g):
        lon = g[lon_col].values; lat = g[lat_col].values; n = len(g)
        if n < 2:
            return []
        return [min(geod.inv(lon[i], lat[i], lon[j], lat[j])[2]
                    for j in range(n) if j != i) for i in range(n)]
    allnn = []
    per = None
    if group_col:
        rows = []
        for k, g in df.groupby(group_col):
            d = nn(g)
            if d:
                allnn += d
                rows.append((k, len(g), round(np.median(d)), round(min(d)), round(max(d))))
        per = pd.DataFrame(rows, columns=[group_col, "n", "median_nn_m", "min_nn_m", "max_nn_m"])
    else:
        allnn = nn(df)
    a = np.array(allnn)
    overall = {"median_nn_m": float(np.median(a)),
               "pct_within_200m": float(100 * np.mean(a < 200)),
               "pct_within_2000m": float(100 * np.mean(a < 2000))}
    return per, overall


# ------------------------------ Extraction ---------------------------------
def build_fc(df, id_col, lon_col, lat_col):
    import ee
    return ee.FeatureCollection([ee.Feature(
        ee.Geometry.Point([getattr(r, lon_col), getattr(r, lat_col)]),
        {"sid": getattr(r, id_col)}) for r in df.itertuples()])


def extract(image, df, scale, reducer="first", radius=None,
            id_col="deployment_id", lon_col="longitude", lat_col="latitude",
            batch=40, verbose=True):
    """Reduce an ee.Image at points (radius=None) or in circular buffers
    (radius in m), batched to stay under getInfo() payload limits.

    reducer: any ee.Reducer factory name -- 'first' (point value),
      'mean'/'median'/'stdDev'/'minMax' (continuous buffer stats), or
      'histogram' (categorical -> {code: pixel_count}, for buffer composition).
    Returns {sid: {band_or_key: value}}. For 'histogram' the value is the
    per-band frequency dict; pass to histogram_to_pct()."""
    import ee
    if reducer == "histogram":
        red = ee.Reducer.frequencyHistogram().setOutputs(["h"])
    else:
        red = getattr(ee.Reducer, reducer)()
    res = {}
    n = len(df)
    for i in range(0, n, batch):
        f = build_fc(df.iloc[i:i + batch], id_col, lon_col, lat_col)
        if radius:
            f = f.map(lambda x: x.buffer(radius))
        out = image.reduceRegions(f, red, scale).getInfo()
        for ft in out["features"]:
            p = dict(ft["properties"]); sid = p.pop("sid")
            if reducer == "histogram":
                res[sid] = p.get("h", {}) or {}
            else:
                res[sid] = p
        if verbose:
            print("  batch %d/%d (%d sites)" % (i // batch + 1, (n + batch - 1) // batch, len(res)), flush=True)
    return res


def histogram_to_pct(hist_by_sid, groups=None):
    """Convert {sid: {code: count}} frequency histograms into per-site
    percentages. If `groups` (a {group_name: [codes]} dict) is given, sum
    within groups; otherwise one column per raw code. Returns a DataFrame."""
    import pandas as pd
    rows = {}
    if groups:
        code2grp = {int(c): g for g, codes in groups.items() for c in codes}
        for sid, h in hist_by_sid.items():
            tot = sum(h.values())
            acc = {g: 0.0 for g in groups}
            if tot > 0:
                for k, v in h.items():
                    g = code2grp.get(int(float(k)))
                    if g:
                        acc[g] += 100 * v / tot
            rows[sid] = acc
    else:
        for sid, h in hist_by_sid.items():
            tot = sum(h.values())
            rows[sid] = {str(int(float(k))): (100 * v / tot if tot else 0.0) for k, v in h.items()}
    return pd.DataFrame(rows).T.fillna(0)


def distance_to_mask(mask_image, neighborhood=256, pixel_m=30):
    """Build an ee.Image of distance (m) to the nearest pixel where
    `mask_image` is 1, via fastDistanceTransform. Deep-interior points beyond
    the neighborhood return a large sentinel -- cap with cap_sentinel().
    Enlarging `neighborhood` past ~256 can make the transform return null
    under EE compute limits; cap instead."""
    import ee
    return mask_image.fastDistanceTransform(neighborhood).sqrt().multiply(pixel_m).rename("dist_m")


def cap_sentinel(series, sentinel=50000):
    """Cap 'no-target-found' distance-transform sentinels at the deepest
    genuinely-measured value. Returns (capped_series, flag_series)."""
    import pandas as pd
    s = pd.to_numeric(series, errors="coerce")
    cap = float(s[s < sentinel].max())
    return s.clip(upper=cap), (s >= sentinel).astype(int)
