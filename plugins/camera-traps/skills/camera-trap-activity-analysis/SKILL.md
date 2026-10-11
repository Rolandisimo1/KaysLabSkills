---
name: camera-trap-activity-analysis
description: "Methods for analyzing animal activity patterns from camera-trap detections (diel activity curves, nocturnality, peak activity time, activity overlap and activity level) and for regressing activity or other per-site measures on covariates across many sites. Covers filtered vs unfiltered detections (activity incidence vs intensity) and the independence interval, sun-anchored time, circular statistics, overlap estimators, how many detections a site needs, a reliability screen, the counting-noise null for count-derived predictors, weight capping, spatial confounding, block cross-validation, and mapping. Use when fitting or comparing activity curves, choosing an independence interval, comparing activity between species, seasons or sites, asking whether activity shifts with people, predators, habitat or climate, or mapping a camera-derived measure. Run camera-trap-qc on the data first."
---

# Camera-trap activity analysis

General methods for activity-pattern work and for any regression of a
camera-derived site measure on covariates. Each rule exists because getting it
wrong produced a plausible, wrong result in a lab project; the numbers below are
from the continental diel-activity analysis (see `diel-activity-conventions`).

Data checks come first and live in `camera-trap-qc`: time zones and per-camera
clock faults (drop bad clocks, never shift them), array definitions, and the
per-bin effort offset needed for sun-anchored time.

## Time

- **Sun-anchored time: 0 = sunrise, 12 = sunset, 24 = next sunrise; night is
  12 to 24.** Drawing it midnight-to-midnight silently puts nocturnal species in
  daylight and still looks plausible. Verify every curve figure against a stored
  measure (for example, recompute the night share from the plotted curve).
- **Sunrise and sunset in local clock hours from true IANA time zones**
  (`timezonefinder` plus `zoneinfo`). Hand-coded zone boundaries fail at state
  lines and in places without daylight saving.
- **Peak time is circular.** Every difference, mean, variance, interval,
  variogram distance and cross-validation error on it uses circular arithmetic.
  A linear difference across midnight is wrong by up to 12 hours. Draw it only
  with a cyclic colormap. This caused two separate bugs in one project.

## Choosing the activity measure

- **Filtered and unfiltered detections measure different things.** Filtering
  to independent events (one record per species per camera within an
  interval) gives how often a species is present at each time of day.
  Unfiltered detections also count groups and animals that linger (feeding,
  area-restricted search). Lab terms: **activity incidence** (filtered) and
  **activity intensity** (unfiltered). Name the filter and its interval in
  every figure and methods section. The published disagreement over
  independence filters (Peral et al. 2022 and the reply) comes from treating
  the two as one quantity; both can be right.
- **The ratio of intensity to incidence by time of day is a result in
  itself**: it shows when animals group or linger. Group size and dwell time
  both vary across the day.
- **The independence interval is also a group-size rule.** Records closer
  together than the interval are merged, so the same choice sets how many
  animals one detection represents. State it, and rerun with a second
  interval when a conclusion depends on grouping.
- Wildlife Insights sequences use a 1-minute gap; many activity studies use 30
  or 60 minutes. Report which one was used.
- Temporal autocorrelation between detections at one camera decays quickly,
  but estimating it needs high abundance; do not rely on it for rare species.

## Comparing activity between groups or sites

- **Overlap coefficient** (overlap package; Ridout and Linkie 2009): use the
  Dhat1 estimator when the smaller sample has fewer than about 50 detections
  and Dhat4 above about 75; give bootstrap confidence intervals (at least 1000
  smoothed bootstrap samples).
- **Activity level** (proportion of the day active; Rowcliffe et al. 2014,
  activity package) assumes every individual is active at the daily peak.
  Compare it between groups; do not read it as an absolute time budget.
- **Compare curves in sun time** when sites span latitudes or seasons: in
  clock time, day length changes the curve's shape.

## How much data a site needs

Reliability is the share of between-site variance that is real rather than
estimation error: `(var_obs - mean(se^2)) / var_obs`. Require above 0.5 before
analyzing a measure spatially; report failing species-measure combinations as
not assessed. Overall activity level failed this screen (median 0.31) in the
continental analysis.

Design guidance: standard errors fall below half the typical between-site spread
at roughly 100 to 200 detections per species per site. Below 50 detections a site
says little about spatial variation.

**Sites, not cameras, are the spatial unit** when cameras are clustered
(median nearest-neighbour distance within a site was 324 m). Define sites by
clustering, and key deployments on `project_id|deployment_id`, since deployment
IDs repeat across projects.

## Counting-noise null for count-derived predictors

Required whenever a predictor is built from detection counts (predator richness,
predator abundance, the focal species' own detection rate); not needed for
environmental covariates.

Activity measures estimated from sparse counts are biased as well as noisy:
random clumping makes a sparse curve look more concentrated. Regressing such a
measure on a count-derived predictor manufactures an effect. In simulation from
one fixed rhythm, concentration read 0.395 at 20 detections against a true
0.338, and a regression on detection count reached P < 0.05 in 18 percent of
runs with no real effect.

Null: hold curve shape at the species' pooled shape; at each site draw counts
from a negative binomial scaled to that site's total, its per-bin effort and its
fitted dispersion; refit the curve, recompute the measure, refit the same model.
Report the fraction of each observed effect the null reproduces.

## Regression on site measures

- **Choose predictors as a research decision**, one per mechanism. No
  composite indices, no automated variable selection. Drop predictors that are
  the same gradient measured twice (nighttime lights and developed land
  correlated with population density at 0.93 and 0.88) and say what that
  prevents you from separating.
- **Univariate tests are not the primary inference**: a univariate coefficient
  includes everything correlated with that predictor.
- **Report collinearity per model**, not pooled; each model uses its own sites
  (pooled max VIF 1.50, per-model max 3.55).
- **Cap inverse-variance weights at the 90th percentile within each model.**
  Uncapped, measures near a bound get their smallest standard errors where they
  carry least information: 7 of 61 models fell below an effective sample size of
  10 sites, one to 1.0. Capping left coefficients nearly unchanged (r = 0.97, no
  sign reversals).

## Spatial confounding

Refit every model with a low-rank spatial smooth added. An effect that
disappears once position enters the model cannot be separated from everything
else that varies across the region and gets no mechanistic reading.

## Cross-validation

Leave out contiguous spatial blocks (400 km at continental scale). Build every
design-matrix parameter from training rows only, including covariate centring
and basis centre positions; a leakage bug here once invalidated a whole
comparison. Report the skill estimate with its interval, not a count of models
beating a threshold, and record the resampling seed.

## Mapping

Only landscape covariates can be mapped; survey-derived predictors (detection
rates, predator counts) are not on a prediction grid. **Refit on
grid-extracted covariates** before predicting to a grid: site values are means
over non-random camera locations and differ from cell values (population density
agreed at only r = 0.55). Compare mean absolute difference between adjacent cells
with the total spread across sites; a surface whose cell-to-cell variation
approaches its total spread is overfitting.

## Presentation

Activity guilds: under 20 percent of activity at night is diurnal, over 80
percent nocturnal. Colour guilds by behaviour. Write-ups follow
`kays-analysis-report-standards`.
