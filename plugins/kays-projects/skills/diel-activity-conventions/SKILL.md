---
name: diel-activity-conventions
description: Analysis conventions for the continental mammal diel-activity project (camera-trap activity curves across the lower 48). Covers the sun-anchored time origin, the per-bin effort offset, circular handling of peak time, sites as the spatial unit, the eight-predictor mechanism model, the counting-noise null for count-derived predictors, weight capping, and the drop-do-not-shift rule for bad clocks. Use when working on diel activity curves, camera-trap activity analysis, or resuming this project.
---

# Diel activity project conventions

Conventions for the continental diel-activity analysis. Each one exists because
getting it wrong produced a real error in this project. Code lives in the
`diel-activity` repository; figures in `figures/dielfigs.py`.

## Time

**Sun-anchored time runs 0 = sunrise, 12 = sunset, 24 = next sunrise. Night is
12 to 24.** Drawing it as midnight-to-midnight silently puts nocturnal species
in daylight and looks plausible. Verify against a stored measure before
trusting any curve figure:

    dielfigs.verify_curve_convention(harmonics)

**Sunrise and sunset must be computed in local clock hours using true IANA time
zones.** Comparing solar sunrise against a clock timestamp is wrong by the
site's longitude offset within its zone plus daylight saving, reaching an hour
at zone edges. Hand-coded zone boundaries fail where borders follow state lines
and where a state does not observe daylight saving. Use `lib/solarclock.py`;
it agrees with published times to within 14 minutes across four zones. An
earlier version of that helper had the bug and its results were retracted.

**Peak time is circular.** Every difference, mean, variance, interval and
cross-validation error metric on it uses circular arithmetic, and it is drawn
only on a cyclic colormap. A linear difference across midnight is wrong by up
to 12 hours and inflates spatial statistics. This produced two separate bugs
here, in variogram pairwise differences and in a cross-validation error metric.

## Effort

**Every count model carries an exact analytic per-bin effort offset.** Per-bin
effort is uniform in clock time but not in sun-anchored time: rescaling to
fixed anchors compresses and stretches the day and night segments unequally,
with within-camera ratios reaching 3.3. Because day length covaries with
latitude and season, omitting the offset produces a believable latitudinal
gradient rather than obvious noise.

## Spatial unit

**Sites, not cameras.** Cameras are deployed in clusters; among cameras
operating simultaneously the median nearest-neighbour distance within a site is
324 metres. Sites are complete-linkage clusters at 25 km.

**Repeat survey years within a site are pooled.** Correct for the among-site
question this project asks. A between-year question would need a different
array definition, and if both framings are in play, build both.

Note the deployment-identifier trap: identifiers are NOT unique across
projects. Around 240 collide. Key on `dep_key = project_id|deployment_id`
everywhere, including when matching exclusion lists.

## Clock errors

**Drop, never shift, without solid evidence.** Fitting an offset per camera
improves apparent fit even on cameras known to be sound, because searching many
candidate shifts always finds one that fits better. Measured false-positive
rate on clean cameras: 44.5 percent, against 60.7 percent on suspect arrays,
so the enrichment is only about 1.4 times and the search cannot identify
individual cameras.

Screen using species with stereotyped schedules as internal clocks, and require
diurnal and nocturnal species to move in OPPOSITE directions at the same camera
before flagging it. Segment by day before testing: partial shifts are the
common case. Draw verification images from inside the affected segment, not
from the whole deployment. Then confirm against the photographs.

## The model

One weighted least squares model per species and measure, eight predictors,
each mapping to one mechanism:

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

**Do not build composite indices and do not run automated variable selection.**
The predictor set is a research decision. Nighttime lights and developed-land
share were dropped from the study: they correlate with population density at
0.93 and 0.88 and are one gradient measured three ways, so disturbance by human
presence cannot be separated from artificial light with these covariates.

**Univariate tests are not the primary inference.** A univariate coefficient is
the total association including everything correlated with that predictor, so
it cannot identify which factor drives a response when predictors covary.

**Report identification per model, not pooled.** Pooled maximum variance
inflation is 1.50; per model the largest is 3.55 and the largest pairwise
correlation 0.78, because each model uses its own subset of sites.

## Weighting

Weights are the inverse squared standard error of each site's measure,
**capped at the 90th percentile within each model**. Uncapped, a measure that
approaches a bound at many sites gets its smallest standard errors exactly
where it carries least information, and the weights collapse: 7 of 61 models
fell below an effective sample size of 10 sites, one to 1.0 with a single site
holding 99.8 percent of the weight. Capping leaves coefficients essentially
unchanged (r = 0.97, no sign reversals).

## Counting-noise null

**Required for any predictor built from detection counts** — here predator
richness, predator abundance and relative abundance. Not relevant to the
environmental covariates.

The response is estimated from binned counts, and estimates from sparse counts
are biased as well as noisy: random clumping makes a sparse curve look more
concentrated than the underlying rhythm. Regressing such a measure on a
count-derived predictor manufactures an effect. In simulation from a single
fixed rhythm, concentration read 0.395 at 20 detections against a true 0.338,
and a regression on detection count reached P < 0.05 in 18 percent of runs with
no real effect present.

Build the null by holding curve shape fixed at the species' pooled national
shape, drawing counts at each site from a negative binomial scaled to that
site's own total, own per-bin effort and own fitted dispersion, refitting the
curve, recomputing the measure and refitting the same model. Report the
fraction of each observed effect the null reproduces.

## Reliability screen

Reliability is the share of between-site variance that is real rather than
estimation error: `(var_obs - mean_squared_se) / var_obs`. Require above 0.5.
Overall activity level is excluded from all spatial analysis at median 0.31.
Four species-measure combinations fail and are reported as not assessed rather
than fitted.

Design guidance: standard errors fall below half the typical between-site
spread at roughly 100 to 200 detections per species per site. Below 50
detections a site contributes little about spatial variation.

## Spatial confounding

Refit every model with a low-rank spatial smooth added. An effect that
disappears when position enters the model cannot be separated from everything
else varying across the continent, and gets no mechanistic reading. Summer heat
and vegetation largely vanish under this control; human disturbance is the most
robust.

## Cross-validation

Leave-one-block-out on contiguous 400 km blocks. Build every design-matrix
parameter from training rows alone, including covariate centring and basis
centre positions: a leakage bug here once made a whole comparison invalid.

**Report the skill estimate and its interval, not the count of combinations
beating a threshold.** Point skills reproduce exactly, but 48 of 183 rows have
a bootstrap lower bound within 0.02 of zero, so the count changes with the
resampling seed. Record the seed.

## Mapping

Only the five environmental covariates can be mapped. Predator and abundance
covariates are not on the prediction grid, and relative abundance is a property
of the survey rather than of the landscape.

**Refit on grid-extracted covariates; do not apply site-fitted coefficients to
grid values.** The two are different quantities: elevation agrees at r = 0.97
and tree canopy at 0.75, but population density at 0.55, because a site value
is a mean over camera locations that are not randomly placed within a cell.

Report the mean absolute difference between adjacent cells against the total
spread across sites. A surface whose cell-to-cell variation approaches its
total spread is overfitting rather than signal.

## Presentation

Guild boundaries are 20 and 80 percent of activity at night, and guild colours
are behavioural, never by which analysis wave introduced a species. Do not
narrate the analysis history in a report: new readers lack the context. Avoid
em-dashes and contrastive-negation framing; state the fact and give the
measurement. Prose deliverables ship as Word documents, not markdown.
