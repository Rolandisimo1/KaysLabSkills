---
name: gps-tracking-analysis
description: Analyze GPS/Argos animal tracking (relocation) data in R with move2, ctmm and amt: Movebank ingest, duplicate-timestamp and outlier cleaning, projection choice, sampling-schedule and effective-sample-size diagnostics, variogram-based continuous-time model selection, location-error calibration, AKDE home ranges, model-based speed and distance, and pairwise interaction estimation (range overlap, encounter location distributions, separation distances, proximity ratios, encounter rates, proximity networks). Also covers packaging an analysis as a MoveApps app (RFunction.R, appspec.json, move2_loc in/out, artefacts). Use when handed a telemetry dataset or asked about home range, space use, track cleaning, collar diagnostics, or contacts between tracked individuals. Triggers: GPS collar data, Movebank study, telemetry, home range, AKDE, variogram, ctmm, move2, as.telemetry, proximity, encounter rate, contact network, MoveApps. For step-selection load `ssf`.
---

# GPS animal tracking analysis

R-first, with `move2` for data handling, `ctmm` for continuous-time modelling
and everything derived from a fitted model, and `amt` for track manipulation
feeding habitat selection. The trusted reference implementations are
`ctmm-initiative/ctmmlearn` (scripts 01 to 10), `ctmm-initiative/ctmmNetwork`
(`automated_movement_networks.R`, a complete multi-individual pipeline), and
the MoveApps app repos under `movestore/`.

## Scope and handoffs

- Step-selection, iSSF/iSSA, used-vs-available, RSS: load `ssf`. Do not
  reimplement it here.
- Restoring the R package library (`amt`, `unmarked`, `secr`, NIMBLE): load
  `wildlife-pop-env` at the start of the session.
- Species-name reconciliation across datasets: load `mdd-taxonomy`.
- Camera-trap data alongside tracks: load `camera-trap-qc`.
- Remote-sensing covariates at fix locations: load `earth-engine`.

## Pipeline order

The order matters because each step's diagnostics decide whether the next step
is admissible. Do not fit models before cleaning, and do not compute any
derived quantity (home range, speed, proximity) before checking effective
sample size.

1. Ingest. 2. Clean (duplicates, then outliers). 3. Set a local projection.
4. Diagnose the sampling schedule. 5. Fit and select a movement model.
6. Calibrate location error if the error scale approaches the movement scale.
7. Estimate the quantity of interest. 8. Report the design limits with the
result, not in a footnote.

## 1. Ingest

`ctmm::as.telemetry()` reads a Movebank CSV (including a zipped one), a
`data.frame`, or a `move`/`move2` object. `move2::movebank_download_study()`
pulls directly from Movebank; pass `sensor_type_id = "gps"` and, for recurring
pulls, `timestamp_start`.

```r
buffalo <- as.telemetry("Kruger African Buffalo, GPS tracking, South Africa.zip")
summary(buffalo)   # per-individual sampling interval and period: read this every time
```

A `telemetry` list holds one object per individual. Keep the list; most `ctmm`
functions accept a list and several (`akde`, `overlap`) require the list form
to produce consistent output. Convert between representations with the
`move2TOtelemetry` / `telemetryTOmove2` MoveApps apps or their code.

## 2. Clean before anything else

Two distinct problems in this order: duplicate timestamps break the model
fitting, and outliers dominate speed and error estimates.

**Duplicate timestamps.** When two records share a timestamp, keep the one
with fewer missing fields rather than an arbitrary one:

```r
x <- x |>
  dplyr::mutate(n_na = rowSums(is.na(dplyr::pick(dplyr::everything())))) |>
  dplyr::arrange(n_na) |>
  move2::mt_filter_unique(criterion = "first") |>
  dplyr::arrange(mt_track_id(), mt_time())
```

**Implausible speeds.** Filter on a species-specific maximum, with units
attached so the threshold is auditable:

```r
max_speed <- units::set_units(1, m/s)
x <- x |> dplyr::filter(mt_speed(.) <= max_speed | is.na(mt_speed(.)))
```

**Outliers: removal must be recursive.** One bad fix creates two bad steps, and
removing it creates a new step between its neighbours that may itself violate the
threshold. Both trusted implementations encode this: `movestore/RemoveOutliers`
wraps the speed filter in a `while` loop (it was changed to a loop in Jan 2024),
and `ctmm-initiative/ctmmMoveApp_outlier` exposes a `Recursive` setting described
as "if removing one point creates a new step that exceeds the speed threshold this
point will also be removed". A single pass is not enough.

The screen order from `movestore/RemoveOutliers`, which is worth following as-is:

```r
Sys.setenv(tz = "UTC")
x <- x |> dplyr::filter(!sf::st_is_empty(x))        # empty geometries error downstream
# 1. impossible coordinates
bad <- st_coordinates(x)[,1] < -180 | st_coordinates(x)[,1] > 180 |
       st_coordinates(x)[,2] <  -90 | st_coordinates(x)[,2] >  90
# 2. Movebank-flagged outliers: visible == FALSE
# 3. accuracy attribute over threshold, e.g. location_error_numerical > 30
# 4. recursive speed filter, per track
maxspeed <- units::set_units(2, m/s)               # animal's ground-speed ceiling
while (any(mt_speed(datai)[-nrow(datai)] > maxspeed, na.rm = TRUE)) {
  datai <- datai[-which(mt_speed(datai) > maxspeed), ]
}
# 5. timestamps in the future (tag clock faults): mt_time(x) > Sys.time()
```

Notes that matter in practice:

- `visible == FALSE` is Movebank's manual outlier flag. When you are the study's
  data manager, flag outliers in Movebank itself rather than in the workflow, so
  the flag travels with the data instead of being re-derived in every analysis.
- The accuracy filter errors if the chosen attribute is non-numeric. Check the
  column type first.
- Return `NULL` (and log it) when no locations survive, rather than an empty object.
- The ctmm route is `outlie()`, which returns error-informed speed and distance
  per fix; threshold on a biological maximum, not a statistical cutoff, and re-run
  after each pass. Set the threshold from the species: `MAX <- 5 %#% "cm/s"` for a
  wood turtle.

```r
OUT  <- outlie(DATA)          # side-effect diagnostic plot
DATA <- DATA[OUT$speed < MAX, ]
OUT  <- outlie(DATA)          # re-run: removing one outlier reveals the next
```

**Verify the screen, do not assume it.** After filtering, re-check the maximum
step length and implied speed per individual. A filter on between-location speed
alone can leave an isolated fix in place when the gap on one side is long enough
to make the implied speed acceptable: a 3.7 km displacement is only 1.5 m/s if the
neighbouring gap happens to be 40 min. Fixes like this survive a speed filter and
show up as long radial spikes out of the core range on a track map, so plot the
tracks after cleaning. Catching them needs either the error-informed `outlie()`
speeds or a test that asks whether a fix is reachable from *any* neighbour in a
time window, not just from the previous one.

**Burst duplicates.** Collars often fire several fixes seconds apart. Thin
against the last *kept* fix (not against the previous row), default 60 s. This
is what `ctmmNetwork` does before fitting, and it prevents bursts from
dominating the variogram at short lags.

## 3. Projection

Distances, speeds and areas are all computed in the projected plane, so the
projection must be locally flat over the data.

```r
projection(buffalo) <- median(buffalo)   # geometric median, azimuthal equidistant, North up
```

`as.telemetry()` defaults to a two-point equidistant projection, which is safer
for migratory tracks but does not preserve North up. In `move2`, use
`mt_aeqd_crs(x, "centroid", "m")` and `sf::st_transform()`. Any pairwise
distance work must be done in the projected object, and all individuals in a
pairwise or population analysis must share one projection. `ctmm` errors with
"multiple projections not yet supported" when they do not.

## 4. Sampling schedule and effective sample size

`dt.plot(DATA)` shows the sorted sampling intervals and exposes collar
malfunctions, duty-cycle changes and gaps. Fix rate determines which questions
are answerable: a 2 h interval cannot resolve a 100 m encounter, and coarse
data cannot support velocity-autocorrelation models.

Effective sample size, not the number of fixes, governs bias. For home-range
area, `DOF[area]` is approximately the sampling period divided by the position
autocorrelation timescale, which is the number of home-range crossings. Check
it in `summary(FIT)$DOF` and gate the analysis on it. For roughly 5% bias:

| Estimator | Minimum `DOF[area]` |
|---|---|
| `ctmm.fit(method = "ML")` | 20 |
| `ctmm.fit(method = "pHREML")` (default) | 4 to 5 |
| `ctmm.boot(method = "pHREML")` | 2 to 3 (slow) |

Ten thousand fixes over two weeks for a range-resident animal can still give
`DOF[area]` near 2. Report `DOF[area]` alongside every home-range number.

## 5. Movement model selection

Always look at the variogram before trusting a fit.

```r
SVF <- variogram(DATA)
plot(SVF, level = c(0.5, 0.95)); zoom(SVF)
```

Read four things: whether it asymptotes (range residency), how long that takes
(position autocorrelation, the home-range crossing time), whether the initial
rise is curved (finite velocity, so an OUF-class model is supportable) or
linear (coarse data, Brownian-class), and whether there is a nugget at the
origin (uncorrelated location error). For irregular data see `variogram()`'s
`fast`, `dt` and `res` arguments and the `variogram` vignette section on
irregular sampling schedules.

```r
GUESS <- ctmm.guess(DATA, interactive = FALSE)
FITS  <- ctmm.select(DATA, GUESS, verbose = TRUE, trace = 3, cores = -1)
summary(FITS)          # ranked by AICc
```

`ctmm.select` walks a nested hierarchy (OUF to OU to IID and relatives), so it
may never attempt IID. Add it explicitly when you want the comparison:

```r
FITS[["IID anisotropic"]] <- ctmm.fit(DATA)
FITS[["IID"]] <- ctmm.fit(DATA, ctmm(isotropic = TRUE))
```

Validate with residuals rather than AICc alone: `RES <- residuals(DATA, FITS[[1]])`,
then `zoom(correlogram(RES, res = 10))`. Use `res = 10` (or `fast = FALSE`) when
the sampling rate drifts. Residual autocorrelation crossing the confidence bands
means the model has not absorbed the autocorrelation.

For non-resident individuals fit `ctmm(range = FALSE)` (BM, IOU). Likelihoods
and AICc of range and non-range models are not comparable; judge these from the
variogram fit, or use `IC = "LOOCV"` for very short tracks.

`ctmm.select` is the slow step and scales with sample size. Save fits
(`save(FITS, file = ...)`) and reuse them. For multi-individual runs, follow
`ctmmNetwork`: per-step OS-level timeouts via `callr` so one non-converging
individual cannot hang the run, plus an on-disk fit cache.

## 6. Location error

Decide by comparing the error scale to the movement scale over one sampling
interval. If the animal moves less between fixes than the collar's error, the
error model is not optional.

- Fit the error model on **calibration data only**: a device left stationary, or
  data collected after an animal died and was not moved. Never run `uere.fit()`
  on tracking data.
- Compare which error covariates are informative (location class, then HDOP,
  then homoskedastic) by AICc across candidate `uere.fit()` objects, and check
  the reduced chi-square style diagnostic; also check whether tags need
  individual error models.
- With no calibration data, supply a prior: `uere(x) <- c(20, 10)` for 20 m 2D
  and 10 m 3D error at HDOP 1, then set `PRIOR$DOF[] <- 2` so the prior carries
  finite weight instead of being treated as exact.
- Then fit with error switched on: `ctmm.guess(DATA, CTMM = ctmm(error = TRUE), interactive = FALSE)`.
- `predict(DATA, FIT)` returns error-smoothed locations; `simulate(DATA, FIT)`
  simulates conditional on the data.

Without an error model, every metre of error is attributed to animal movement,
which inflates speed and diffusion estimates.

## 7. Home range and population range

```r
AKDE  <- akde(DATA, FIT)                    # autocorrelation-informed
wAKDE <- akde(DATA, FIT, weights = TRUE)    # for irregular sampling; slower
summary(wAKDE)                              # area estimate with CI
```

Use `weights = TRUE` whenever the sampling schedule is irregular or the duty
cycle changed; it downweights oversampled periods. Keep the default
`debias = TRUE`, since the Gaussian reference function over-smooths. Conventional
KDE on autocorrelated fixes underestimates range area, so `akde(DATA, IID)` is
for demonstrating that bias, not for reporting.

For several individuals, estimate together so the grid is shared:

```r
AKDES <- akde(buffalo, FITS, weights = TRUE)   # consistent grid across individuals
```

Population-level summaries: `meta(AKDES)` runs the hierarchical meta-analysis
and forest plot and is the correct way to get a mean home-range area with a CI;
averaging point estimates by hand discards the individual uncertainties.
`mean(AKDES, sample = FALSE)` averages the densities themselves (mind the
`sample` argument for correct CIs), and `pkde()` estimates a population range
that does not collapse toward the sampled individuals.

## 8. Speed and distance

Do not sum straight-line steps: that estimator is biased low at coarse fix
intervals and biased high when location error is present. Use the model-based
estimators (`speed()`, `speeds()` on a fitted model), which return CIs. For
descriptive per-individual daily summaries in `move2`, `mt_distance()` and
`mt_speed()` are fine, but label them as path-length statistics conditional on
the fix interval rather than as travel speed.

## 9. Interactions between individuals

Four distinct claims, in increasing data demand. Say which one is intended
before choosing a method. Overlap needs no simultaneity; correlated movement
needs concurrent fixes; encounters need a distance threshold and a fix rate
fine enough to resolve it; indirect (cue-mediated) response needs neither
simultaneity nor proximity.

**Range overlap.** `overlap(AKDES)` returns a bias-corrected overlap matrix with
confidence intervals (`OVER$CI[, , "est"]`, pairwise CIs at
`OVER$CI["A", "B", ]`). Two hard requirements: the paired UDs must be on a
common grid, and they must be estimated jointly.

```r
overlap(akde(list(buffalo$Pepper, buffalo$Queen), list(FITS$Pepper, FITS$Queen)))  # correct
overlap(list(akde(buffalo$Pepper, FITS$Pepper), akde(buffalo$Queen, FITS$Queen)))  # WRONG: incompatible grids
```

Uncorrected overlap is biased low. Overlap answers whether animals share space,
never whether they were there at the same time.

**Encounter locations.** `cde(AKDES[c("A","B")])` estimates the conditional
distribution of encounters, where encounters are expected given independent
movement between them. This is the informative product for asking where
competition, predation or transmission should concentrate; plot it with
`plot(DATA_pair, UD = CDE)`.

**Separation distances.** `distances(DATA_pair, FITS_pair)` predicts the
distance between two animals at each timestamp with confidence intervals, so it
works through gaps and mismatched schedules. Report the CIs: a 30 m point
estimate between collars with 30 m error is not a contact.

**Proximity ratio.** `proximity(DATA_pair, FITS_pair)` gives the ratio of
observed to expected separation under independent movement. Below 1, closer than
independent; 1, independent; above 1, farther apart than independent. A CI
spanning 1 licenses no conclusion, and many dyads legitimately land there. For
network edge weights, `ctmmNetwork` uses `signed_weight = -log(estimate)`
(positive means together) and classifies dyads by whether the CI clears 1. Skip
pairs with less than about a day of shared tracking; `proximity()` is slow.

**Encounter rates.** `encounter(AKDES, method = "PDF")` gives relative encounter
rates. For empirical counts from `distances()`, the encounter radius is an
arbitrary choice and the count is monotone in it, so report a sensitivity curve
rather than a single threshold:

```r
enc_rad <- 1:1000
N <- sapply(enc_rad, function(r) sum(DISTS$est <= r))
plot(N ~ enc_rad, type = "l", xlab = "Encounter radius (m)", ylab = "Encounters")
```

**The independent-motion null.** Simulate each animal from its own fitted model
at the observed timestamps and recompute the statistic; that is the baseline any
proximity claim is measured against.

```r
a_sim <- simulate(FITS$A, t = DATA$A$t)
b_sim <- simulate(FITS$B, t = DATA$B$t)
distances(list(a_sim, b_sim), FITS[c("A","B")])
```

The alternative null is path randomization, which holds the trajectories fixed
and shuffles their temporal alignment; it leaves shared habitat preference in
the null, so it separates social attraction from mutual attraction to the same
places. The two nulls answer subtly different questions. State which you used.

**Threshold-based proximity and networks.** For herd or group data, per-timestep
neighbour counts within a radius (`group_proximity`) are the practical approach:
interpolate to a common time grid (`mt_interpolate(x, "10 min", omit = TRUE)`),
require a minimum number of individuals present per timestep before computing
distances, project first, then a distance matrix per timestep with the diagonal
set to NA. Add local time and day/night with `lutz::tz_lookup_coords()` and
`suncalc::getSunlightTimes()` rather than assuming UTC is interpretable. For
network metrics, build edges with `spatsoc` and use its null models; edges exist
only relative to the spatial and temporal thresholds chosen, and networks built
under different thresholds are not comparable.

**Interspecific work** uses the same machinery with two cautions: range-scale
overlap and fine-scale avoidance routinely disagree, and asymmetric
(predator-prey) interaction is not what the symmetric attraction statistics
assume. Report the dyad-level concurrent coverage for every pair.

## 10. Behavioural segmentation

For behavioural states use HMMs (`momentuHMM`, `moveHMM`) on regularized tracks,
not thresholds on step length. Be sceptical of reading behaviour off space-use
summaries. When the interaction is expected to act on behavioural mode rather
than on step geometry, the state-based formulation is the right one.

## Packaging as a MoveApps app

An app is a git repo forked from `movestore/Template_R_Function_App`. Only
these are bundled into the running app: `RFunction.R`, everything under
`./src/app/` (which you must `source()` yourself), directories declared in
`appspec.json` under `providedAppFiles`, plus `appspec.json` and `README.md`.
Nothing else ships.

**`RFunction.R`** is the entrypoint and the filename is fixed. It receives the
input data as its first argument and **must return the data object** to pass to
the next app in the workflow. Input and output types are `move2::move2_loc`
(legacy `moveStack` inputs are converted to `move2` automatically). Settings
declared in `appspec.json` arrive as named arguments.

```r
rFunction = function(data, radius = NULL, ...) {
  if (is.null(radius)) {
    logger.info("No radius given; defaulting to 1000 m")
    radius <- 1000
  }
  ## work here
  return(data)
}
```

Log with `logger.fatal/error/warn/info/debug/trace()`, not `print()` or
`message()`. Write artefacts (CSV, PNG, shapefiles) into `APP_ARTIFACTS_DIR`.

**`appspec.json`** declares `settings` (each with `id`, `name`, `description`,
`type` such as `STRING`, `INTEGER`, `USER_FILE`, and usually `defaultValue`),
`dependencies.R`, `providedAppFiles`, `license`, `keywords`, `people` and
`references`. Every setting `id` must match both the argument name in
`rFunction()` and the key in `app-configuration.json` used for local testing.

**Local testing** runs through `sdk.R` with paths and behaviour set by `.env`:
`SOURCE_FILE` selects one of the sample inputs in `data/raw/` (the template
ships `move2_loc` in LatLon and Mollweide plus a `telemetry` list),
`OUTPUT_FILE`, `APP_ARTIFACTS_DIR`, `CLEAR_OUTPUT`, `CONFIGURATION`. `.env` is
hidden in RStudio. Unit tests go in `tests/testthat/`. `renv` is opt-in
(`renv::activate()`); build and run the `Dockerfile` when a failure looks like a
missing system library.

**`README.md`** is the user-facing documentation and the template's headings are
the required content: description, documentation, application scope (which taxa
it was developed on), required data properties (fix rate, range residency),
input and output type, artefacts, settings with units, how the input data are
modified, common errors, and null/error handling per setting. Filling these in
is what makes an app usable by someone else; leaving the template text in place
is the most common defect in published apps.

## Pitfall checklist

- Overlapping separately-estimated AKDEs (incompatible grids). Estimate jointly.
- Reporting a home-range area without `DOF[area]`.
- Conventional KDE on autocorrelated fixes, or unweighted AKDE on irregular data.
- Fitting before removing duplicate timestamps and outliers.
- `uere.fit()` on tracking data instead of calibration data.
- Summing straight-line steps as a speed or path-length estimate.
- A single encounter radius with no sensitivity curve.
- Proximity or distance point estimates reported without CIs, or a contact
  claimed at a separation comparable to the location error.
- Mixed projections across individuals in a pairwise analysis.
- Interaction conclusions from dyads with little concurrent coverage.
- Interpreting a proximity ratio whose CI spans 1.
- Assuming UTC timestamps are biologically interpretable; derive local time.
- Network metrics from a minority of the population without a tagging-fraction
  sensitivity analysis.

## Key references

Data and packages: `move2` ([Kranstauber et al. 2024](https://doi.org/10.1111/2041-210X.14383)),
`ctmm` ([Calabrese et al. 2016](https://doi.org/10.1111/2041-210X.12559)),
`amt` ([Signer et al. 2019](https://doi.org/10.1002/ece3.4823)),
`momentuHMM` ([McClintock & Michelot 2018](https://doi.org/10.1111/2041-210X.12995)),
the Movebank data model ([Kranstauber et al. 2011](https://doi.org/10.1016/j.envsoft.2010.12.005)),
and the wider package landscape ([Joo et al. 2019](https://doi.org/10.1111/1365-2656.13116)).

Home range: AKDE ([Fleming et al. 2015](https://doi.org/10.1890/14-2010.1)),
autocorrelation and bias ([Noonan et al. 2019](https://doi.org/10.1002/ecm.1344)),
practical guide ([Silva et al. 2021](https://doi.org/10.1111/2041-210X.13786)),
missing and irregular data ([Fleming et al. 2018](https://doi.org/10.1002/eap.1704)).

Interactions: overlap inference ([Winner et al. 2018](https://doi.org/10.1111/2041-210X.13027)),
utilization-distribution overlap indices ([Fieberg & Kochanny 2005](https://doi.org/10.2193/0022-541X%282005%2969%5B1346:QHOTIO%5D2.0.CO;2)),
encounter location distributions ([Noonan et al. 2021](https://doi.org/10.1111/2041-210X.13597)),
dynamic interaction indices audited ([Long et al. 2014](https://doi.org/10.1111/1365-2656.12198)),
path randomization ([Spiegel et al. 2016](https://doi.org/10.1111/2041-210X.12553)),
telemetry social networks ([Robitaille et al. 2019](https://doi.org/10.1111/2041-210X.13215)),
sampling design for GPS-based social studies ([He et al. 2022](https://doi.org/10.1111/2041-210X.13999)),
encounter concepts ([Das et al. 2023](https://doi.org/10.3389/fevo.2023.1230890)).
