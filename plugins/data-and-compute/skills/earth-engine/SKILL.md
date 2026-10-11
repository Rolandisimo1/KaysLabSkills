---
name: earth-engine
description: Extract raster values from Google Earth Engine at point locations - point sampling, buffer statistics, categorical composition histograms, and distance-to-feature - for adding remote-sensing covariates (land cover, climate, terrain, NDVI, human footprint) to ecological or spatial models. Covers service-account authentication for headless/sandbox use, asset verification, and choosing buffer radii from point spacing. Includes MapBiomas Brazil land cover as a worked example.
---

# Google Earth Engine point extraction

Reduce any Earth Engine raster (`ee.Image`) to per-point covariates: point
values, buffer statistics (mean/median/stdDev), categorical composition
(histograms -> %), and distance-to-feature. General-purpose - works for land
cover, NDVI/EVI, climate, terrain, human-footprint, or any EE asset.

Ships helpers in `kernel.py` (auto-loaded): `gee_init`, `check_asset`,
`point_spacing`, `extract`, `histogram_to_pct`, `distance_to_mask`,
`cap_sentinel`. Bundled reference constants for the MapBiomas Brazil worked
example: `MAPBIOMAS_ASSETS`, `MAPBIOMAS_LEGEND`, `MAPBIOMAS_ECO_GROUPS`,
`MAPBIOMAS_NATIVE_CODES`.

Run in a Python env with `earthengine-api`, `pandas`, `pyproj` (the `geo` env
has these). Helpers defer `import ee` so the skill loads before EE is installed.

## 1. Authentication (service account, headless)

A sandbox/headless kernel can't do browser OAuth - use a **service-account
JSON key**. One-time setup in Google Cloud Console for an EE-registered project:

1. IAM & Admin -> Service Accounts -> create one, create a JSON key, save locally.
2. Grant the SA two roles on the project (IAM -> **Grant access**, add BOTH in one grant so the second doesn't replace the first):
   - **Earth Engine Resource Writer** - read-only *Viewer* is NOT enough; `reduceRegions`/`sampleRegions` are server-side computations needing `earthengine.computations.create`, which Writer provides.
   - **Service Usage Consumer** - else `Caller does not have required permission to use project`.
3. If the project isn't EE-enabled, register the SA at code.earthengine.google.com/register.

Gotchas:
- Role changes take 2-5 min to propagate - wait and retry.
- If an **org policy** (`constraints/iam.allowedPolicyMemberDomains`, "Domain Restricted Sharing") blocks adding the `@...gserviceaccount.com` principal, a GCP **org admin** must grant an exception. Fallback: run the job in the EE Code Editor as your own org identity, `Export.table.toDrive`, read the CSV back.
- In a sandbox, allow `oauth2.googleapis.com` + `earthengine.googleapis.com`. Path-style `storage.googleapis.com` is not needed for `getInfo()`-based sampling.

```python
info = gee_init("keys/<project>-xxxx.json")   # reads client_email + project from the key
print(info)   # {'service_account': ..., 'project': ..., 'check': 2}
```

## 2. Verify the asset and band before trusting it

Collection/version names drift; confirm the asset and the band you want exist:

```python
check_asset("projects/mapbiomas-public/assets/brazil/lulc/collection10/mapbiomas_brazil_collection10_coverage_v2",
            kind="image", band="classification_2024")
# -> {'bands': [...], 'has_band': True}
```
For a time series, use `kind="image_collection"`. Never hard-code an asset ID
from memory into a pipeline without a `check_asset` first.

## 3. Choose buffer radii from point spacing

A buffer whose diameter exceeds typical nearest-neighbor spacing overlaps
neighbors, so those covariates are spatially autocorrelated pseudoreplicates.
Measure first:

```python
per, overall = point_spacing(df, group_col="subproject_name")   # group_col optional
print(overall)   # {'median_nn_m':487, 'pct_within_200m':15, 'pct_within_2000m':84}
```
Interpretation: if most points have a neighbor within 2*radius, that radius
overlaps. Prefer a small radius for local composition + one larger radius for
landscape context; pick the large-radius measure that is *least* redundant with
its small-radius twin (regress one on the other, keep low-R^2 ones). A
biome-agnostic aggregate (e.g. % native vegetation) often travels best across
regions.

## 4. Extract

`extract(image, df, scale, reducer=..., radius=...)`:
- **Point value** (categorical or continuous): `reducer="first"`, `radius=None`, `scale`=native res.
- **Buffer statistic** (continuous layer, e.g. NDVI/elevation): `reducer="mean"` (or `median`/`stdDev`), `radius=<m>`.
- **Buffer composition** (categorical layer, e.g. land cover): `reducer="histogram"`, `radius=<m>` -> `{sid: {code: count}}`, then `histogram_to_pct`.

```python
lulc30 = ee.Image(MAPBIOMAS_ASSETS["lulc_30m"]).select("classification_2024")
pt    = extract(lulc30, df, scale=10,  reducer="first")                 # point class
h100  = extract(lulc30, df, scale=30,  reducer="histogram", radius=100) # composition
```
~300 points take ~1 min. Batches of ~40 features stay under `getInfo()` limits.

## 5. Composition percentages, with optional grouping

```python
g100 = histogram_to_pct(h100, groups=MAPBIOMAS_ECO_GROUPS)  # forest/savanna/... %
# groups=None -> one column per raw code (then lump yourself)
```
When a categorical layer has a long tail of rare classes, group into ecological/
functional classes before modeling - one covariate per raw class yields many
mostly-zero columns that break PCA and inflate the model.

## 6. Distance to a feature (fragmentation, edges, water)

```python
nat = lulc30.remap(MAPBIOMAS_NATIVE_CODES, [1]*len(MAPBIOMAS_NATIVE_CODES), 0)
dist_img = distance_to_mask(nat.eq(0))          # distance to nearest NON-native pixel
d = extract(dist_img, df, scale=30, reducer="first")
edge = pd.Series({k: v["dist_m"] for k, v in d.items()})
edge_capped, edge_flag = cap_sentinel(edge)     # cap deep-interior 'no-edge' sentinels
```
`fastDistanceTransform` returns a large sentinel where no target pixel is within
the search neighborhood; `cap_sentinel` caps at the deepest measured value and
flags those points. Enlarging the neighborhood past ~256 can make the transform
return null under EE compute limits - cap instead.

## 7. Reduce covariates before modeling

Same-layer buffer % at two radii are often near-duplicates (r>0.8) - keep one
radius per class. Run a correlation matrix + PCA; drop within-class redundancy,
not across-class structure. For a small effective N keep few terms and check VIF
(<~3). Compositional covariates that trade off (e.g. forest vs savanna % in the
same buffer) are collinear by construction; use one, use the point class, or
report as a block.

## Notes
- Point habitat class can serve as a **detection** covariate in occupancy models (visibility/animal behavior differs by cover type), often improving fit independent of its occupancy role.
- Match the raster year to the survey; `check_asset` for the `classification_<year>` band.
- MapBiomas constants are Brazil-specific; other MapBiomas territories (Amazonia, Chaco, Indonesia) and other providers are separate asset paths - verify with `check_asset`.
