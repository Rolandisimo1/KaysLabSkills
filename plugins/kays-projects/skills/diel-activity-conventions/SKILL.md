---
name: diel-activity-conventions
description: "Project-specific settings for the continental mammal diel-activity analysis (camera-trap activity curves across the lower 48): repository layout and helper functions, the 25 km site definition, the eight-predictor mechanism model and why predictors were dropped, which effects survived spatial controls, and what was mapped. Use when working on or resuming this project. General methods (sun-anchored time, circular peak time, reliability screen, counting-noise null, weight capping, block cross-validation, mapping) are in camera-trap-activity-analysis; load both."
---

# Diel activity project conventions

Settings for the continental diel-activity analysis. The general rules behind
them are in `camera-trap-activity-analysis` and `camera-trap-qc`; this file
records the choices made for this project and where the code lives.

## Code

- Repository: `diel-activity`. Figures: `figures/dielfigs.py`.
- Verify any curve figure with `dielfigs.verify_curve_convention(harmonics)`.
- Sunrise and sunset in local clock hours: `lib/solarclock.py` (agrees with
  published times within 14 minutes across four zones). An earlier version of
  that helper ignored the longitude offset within a zone and its results were
  retracted.

## Sites

- Sites are complete-linkage clusters of cameras at 25 km.
- Repeat survey years within a site are pooled, which suits the among-site
  question. A between-year question needs a different array definition; if both
  framings are in play, build both.
- Key deployments on `dep_key = project_id|deployment_id`; about 240
  deployment IDs collide across projects. Use the same key when matching
  exclusion lists.

## Clock screening in this dataset

Fitting a per-camera offset flagged 44.5 percent of known-clean cameras against
60.7 percent on suspect arrays (about 1.4 times enrichment), so offset search
cannot identify individual bad cameras here. Use the opposite-direction test
with diurnal and nocturnal sentinel species described in `camera-trap-qc`.

## The model

One weighted least squares model per species and measure:

| Mechanism | Predictor |
|---|---|
| human disturbance | population density, 1 km, log |
| agriculture | cropland share, 5 km |
| vegetation | tree canopy cover, 1 km |
| terrain | ruggedness, 5 km |
| summer heat | max temperature of hottest month, 1 km |
| predator richness | carnivore species detected at the site |
| predator abundance | summed carnivore detection rate, log |
| relative abundance | focal species detections per camera-hour, log |

Nighttime lights and developed-land share were dropped (r = 0.93 and 0.88 with
population density), so disturbance by human presence cannot be separated from
artificial light in this study. Predator richness, predator abundance and
relative abundance require the counting-noise null.

## Results that shape interpretation

- Reliability screen: overall activity level is excluded from all spatial
  analysis (median 0.31); four species-measure combinations fail and are
  reported as not assessed.
- Spatial smooth control: summer heat and vegetation effects largely vanish;
  human disturbance is the most robust.
- Cross-validation: 400 km blocks. 48 of 183 rows have a bootstrap lower bound
  within 0.02 of zero, so report skill with intervals and record the seed.
- Mapping: only the five environmental covariates are mapped, refitted on
  grid-extracted values.

## Presentation

Guild boundaries 20 and 80 percent of activity at night; guild colours are
behavioural, never by analysis wave. Do not narrate the analysis history in a
report.
