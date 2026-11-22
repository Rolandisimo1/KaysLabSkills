---
name: camera-inat-stream-agreement
description: "Standard workflow for integrated camera-trap and iNaturalist models: which parameter is the reportable population trend, the theta1 congruence metric and camera-only control that decide whether the two streams agree, and the mandatory urban-rural screen. Load BEFORE building any figure, map, table or report section that shows a trend, an abundance or intensity surface, a change or period-difference map, covariate effects, or any comparison of the camera and iNaturalist streams -- not only when writing conclusions. Also use when the two streams disagree, when deciding whether a pattern is ecology or an observation artifact, when asked how well the streams agree or what each stream contributes, and when interpreting mu, lambda, psi, theta0, theta1, year_beta, year_var or total_var_beta."
metadata:
  authored_via: "claude-science"
  published_by: "agent"
  published_at: "2026-10-06T00:54:59.683Z"
  authored_by: "agent"
  authored_at: "2026-10-01T14:53:06.468Z"
  authoring_session: "183aba19-810a-4a8c-beef-ca2c06d952db"
  last_modified_by: "agent"
  last_modified_at: "2026-10-06T00:54:59.679Z"
---

# Camera / iNaturalist stream agreement

The standard workflow for trends from the joint camera-trap + iNaturalist
occupancy-intensity model. Three things that must happen every time, and one
model extension for when the screen flags something.

## 0. Checklist, before any figure or table leaves your hands

This skill has repeatedly been skipped at the moment it was most needed,
because the work in hand looked like figure-building rather than like
"reporting a trend". It is the same workflow either way. Run these four
checks against anything that shows a trend, a surface, a change map, or a
comparison of the two streams.

1. **Name the quantity, in the figure itself.** `psi` is camera occupancy and
   carries `year_beta`, the reportable trend. `lambda` is the shared abundance
   intensity and carries `total_var_beta`. `mu` is the expected iNaturalist
   record count and carries `theta1 * total_var_beta`. Three different
   quantities with three different trends; a panel that does not say which one
   it is showing will be read as the reported trend.
2. **Quote theta1 with its interval, against BOTH thresholds** (section 2a),
   before any other statement about whether the streams agree. If you are
   writing a sentence comparing the streams and it does not contain theta1,
   you have reinvented a worse version of this metric.
3. **Say whether the camera-only control exists** (section 2b). If it has not
   been run for the window in hand, say so in the artifact rather than
   leaving the comparison looking complete.
4. **Say whether the urban-rural screen has been run** (section 3). Its
   default outcome is "not assessed", which is not agreement.

If any of 2-4 is unavailable for the window being reported, publish a
coverage table saying which of the three assessments exist and which do not.
A reader cannot tell a missing assessment from a passed one.

### `mu` is not the abundance surface

Measured on the eleven five-year fits (2026-11-20): the per-cell change in
`mu` matches `theta1 * total_var_beta` to a mean error of 0.97 percentage
points per year, against 6.42 for the reading that treats `mu` as abundance.
The two species whose covariates barely move -- nine-banded armadillo and
collared peccary -- match the first to two decimal places.

So `mu_snapshots` holds the expected iNaturalist **record count**, not
abundance. Relative abundance is recovered as `log(lambda) = log(mu)/theta1`
up to an additive constant, which cancels from both the spatial pattern and
the change. The recovery reproduces `total_var_beta` to a mean of 2.4 points
per year, the residual being genuine annual-covariate variation.

**`reportlib/figures_maps.py:fig_abundance` plots `mu_mean` under the title
"Relative abundance surfaces" and is wrong on this point.** Figures built
from it in earlier reports carry that mislabel.

Do not invert `mu` when `theta1` is near zero: the division amplifies without
limit, and a `theta1` interval spanning zero means there was no abundance
signal in the records to recover.

### The surface is shared; only its year coefficient is not

Verified against `model_code_national_scalar.R`: `link_occ_intercept`,
`MWMT_effect`, `MCMT_effect` and all nine `occ_beta` covariate effects appear
in BOTH the `cloglog(psi[i])` block and the `calcIntensity` block. **The
spatial surface is jointly informed by the camera and iNaturalist likelihoods
and by the covariates.** Calling it an iNaturalist product is simply wrong
about this model.

The only parameter that differs between the two blocks is the year
coefficient: `psi` carries `year_beta`, the intensity carries
`total_var_beta`. So the surface *as fitted* changes at the iNaturalist rate.
Before correction, three of eleven five-year species had abundance maps moving
opposite to their own reported trend -- California ground squirrel, groundhog
and eastern chipmunk.

**Anchor the change panel rather than captioning around it.** Year enters the
log-intensity linearly and identically in every cell, so the swap is a
constant shift that leaves spatial variation intact:

    dlog_anchored = dlog_fitted - total_var_beta * (span / sd_inat)
                                + year_beta      * (span / sd_cam)

with `sd_inat` and `sd_cam` the two `year_sd` values in the run's
`year_scaling` file -- the blocks standardise year differently, so using one
scaling for both is wrong. This took sign disagreements from three to one and
the median gap between surface and reported trend to 0.76 pp/yr. Implemented
in `reportlib/figures_products.py:abundance_change`, which returns both
`as_fitted_pct_yr` and the anchored `pct_per_year`.

The window is **2021-2025**. There is no 2020 surface on the five-year fits;
only the ten-year runs (bobcat, white-tailed deer) reach back that far.

## 1. Report the camera-anchored trend, never the summed one

The model carries two trend parameters. `year_beta` sits in the camera
occupancy submodel. `year_var` is an iNaturalist-only addition, and
`total_var_beta = year_beta + year_var` is what the iNaturalist likelihood
sees.

**`year_beta` is the reportable population trend.** `year_var` is a *sink*
that absorbs iNaturalist-specific temporal signal, which is what keeps
`year_beta` camera-identified. Reporting `total_var_beta` reports the
opportunistic stream's trend and is the analogue of quoting the iNaturalist
intensity field instead of camera occupancy in the source paper.

This is not a small correction. For bobcat the two differ in sign:
`year_beta` is +1.0%/yr while `total_var_beta` is -3.4%/yr. A report built on
the summed parameter would have stated a bobcat decline.

**Convert to percent per calendar year before comparing anything.** The two
submodels standardise their year covariate on different distributions, so the
raw coefficients are not on a common scale and their sum mixes two scales.
`mu`-derived trends are a THIRD quantity: a trend fitted to `mu` is the
iNaturalist parameter attenuated by `theta1` (0.52-0.85 in practice), so it
runs shallower than either coefficient. Any figure showing one of these must
name which, in the figure, not only in the caption.

## 2. The agreement decision rule

Camera data is the gold standard; iNaturalist extends coverage but its survey
effort is unmeasured, so it corroborates rather than carries the result.

### 2a. theta1 is the PRIMARY agreement metric. Report it for every species.

`theta1` is the exponent linking the two streams' intensities in
`calcIntensity_SVC`:

    log(mu) = theta0 + theta1 * log(sum(lambda))

It is the model's own statement about whether the streams correspond, and it is
the metric Goldstein et al. use for exactly this purpose, so a reviewer already
knows how to read it. **Quote theta1 with its 95% interval before any other
agreement diagnostic.**

theta1 is an exponent, so read it as a multiplier: a cell with twice the
camera-side abundance yields `2^theta1` times the iNaturalist records. **There
are TWO thresholds, not one, and the healthy state is strictly between them.**

- **theta1 = 0 is the no-agreement value.** The iNat expected count becomes
  constant across cells, so records carry NO spatial information about
  abundance. **An interval that includes 0 means the stream cannot be shown to
  track the camera surface at all** -- its contribution to the shared surface
  is then whatever its own sampling pattern is. Negative is worse than useless:
  records higher where animals are fewer.
- **CI strictly inside 0 to 1** -> partial correspondence. iNaturalist
  under-responds to real abundance differences, which is the normal and healthy
  state for this fleet. The joint camera-anchored trend is safe to report.
- **CI reaches or exceeds 1** -> proportional or over-responding. No observer
  behaviour plausibly produces over-response, so this is the signature of the
  iNat pattern tracking something other than abundance (observer density, road
  access, a few heavily visited sites) with theta1 absorbing the distortion.
  Treat the joint trend as unreportable until a camera-only fit confirms it.

**Judge on the interval, never the mean.** American badger's mean of 0.33 sits
squarely in the healthy band while its interval (-0.14, 1.22) spans BOTH
thresholds, so it is uninformative rather than healthy.

## theta_space and theta_time

theta1 as the model fits it is a single scalar pooled over every year
(`theta0 = double(0)`, `theta1 = double(0)` in the model code). Call that
**theta_space**: across the country, do records track abundance? The same
quantity estimated separately within each year is **theta_time**: is that
relationship the same now as it was six years ago?

theta_time is measurable outside the model -- per year, regress each cell's
effort-corrected iNaturalist rate on a camera-derived relative abundance held
fixed across years, in logs; the slope is that year's coupling. **These
estimates are NOT on theta_space's scale** (the pooled version of that
estimator ran 0.16-0.83 across species where the fitted models give 0.42-0.56).
Read the slope over time, never the level, and do not quote them as theta
values.

**Standing decision: report theta_time as a diagnostic, do NOT correct the
trend for it.** Measured over 2019-2025 on 23 of 34 species, 7 have drift
intervals excluding zero -- 4 strengthening, 3 weakening. The camera-only
control is the direct test of whether that contaminates the reported
camera-anchored trend, and it comes back clean: median displacement between
joint and camera-only estimates is 1.58 pp/yr for the drift species against
2.65 pp/yr for the rest, with |drift| against |displacement| at rho = -0.12
(p = 0.60). The iNaturalist-only trend increment is absorbing the drift, which
is the escape-valve structure working as designed. Adding a drift parameter
would mean refitting the fleet plus a simulation study, against a measured
benefit near zero for the headline result.

Three places it still matters:

- **Anything reporting the iNaturalist-side quantity** -- the intensity
  surfaces and period-change maps -- is driven by the iNaturalist side and is
  NOT protected by the escape valve. A drifting coupling distorts the relative
  heights of those time slices. Carry it as a caveat there.
- **A species whose theta_time crosses zero** has records that no longer point
  at the animals. American badger runs +0.52 (2019) to -0.15 (2025), which also
  explains why its pooled theta_space interval is uninformative: a scalar
  fitted to a quantity that changed sign underneath it.
- **Extrapolation beyond 2019-2025** is not licensed. Camera coverage before
  2019 is too sparse to build a reference from.

What drives it: cell-level record growth aligned with camera-measured abundance
predicts the drift across species (rho = +0.65, p = 0.0008); alignment with
human population does not (rho = +0.15, p = 0.51), being near-universal and so
unable to explain species-level differences. Note the metric cannot separate
observers finding the species better from the species genuinely increasing
where cameras already detect it.

Revisit this decision if a species with large camera-only displacement also
turns out to have large drift. The steep-decline western species are a blind
spot on both diagnostics -- too few camera-monitored cells for either.

**The gate, measured on this fleet (v2u, 2026-10-17):** among the 13 species
that resolved a camera direction and had a camera-only control, every species
whose theta1 interval reached 1 failed the camera-only check (2 of 2), and only
one of eleven that stayed below 1 failed. So **theta1_hi >= 1 means do not
report the joint trend without a camera-only fit in hand.**

Why this is primary rather than the interval-width and deployment-count
correlates: it has a mechanism rather than a correlation, and it is available
from the joint fit ALONE, so it screens a species before any control fit is
built. As a predictor of displacement MAGNITUDE it is weaker than those
correlates (Spearman +0.28, p=0.17, against +0.60 for joint CI width) -- it is a
gate, not a dose-response.

Fleet values as of 2026-10-17 (25 fitted species): median 0.556, range 0.304
(northern raccoon) to 2.241 (California ground squirrel). Twenty are sub-linear,
four include 1 (badger, porcupine, puma, western gray squirrel), one is
super-linear (California ground squirrel). **Do not write that theta1 is
sub-linear for every species** -- that was true of the superseded v2b fits and
is false on the current ones.

### 2b. Then the camera-only control, which tests whether it mattered

theta1 says whether the streams correspond; the camera-only fit says whether
non-correspondence actually moved THIS species' trend. Refit with the iNat
likelihood removed and compare:

- **Camera-only resolves the same direction** -> the joint estimate is anchored;
  report it, since it is the more precise of the two.
- **Camera-only spans zero or flips sign** -> do not report the joint trend as a
  population trend. Report camera-only, or report the species as unresolved.

What integration is worth on this fleet, measured over the 26 species with both
fits: adding iNaturalist narrows the camera trend interval by 14% (median 7.8 ->
6.7 pp/yr) and resolves no additional species (14 either way; three gain a
direction, three lose one). Where both resolve, all 11 agree in sign, median
difference 0.97 pp/yr. So for the TREND specifically the second stream adds
modest precision, not a qualitative change; its value is in the spatial and
climate surfaces, the covariate effects, and the longer temporal window.

### 2c. Per-stream reporting

- **Streams agree** -> report the camera-anchored trend; the iNaturalist
  stream is not under suspicion.
- **Streams oppose in direction** -> report the camera trend and flag the
  iNaturalist stream as questioned. Do not average them and do not pick the
  more convenient one.
- **The comparison is underpowered** -> report neither as agreement. A wide
  interval is "not assessed", not "flat". Read the contrast off its
  INTERVALS, never its signs: a camera contrast of +-12 points could not have
  detected a difference if one existed.

Report the per-stream trends and their difference with an interval, not two
point estimates side by side.

## 3. The urban-rural screen, on every species

**Why it is mandatory rather than diagnostic.** The iNaturalist stream is
about twice urban-weighted while cameras are balanced -- measured
urban:rural sampling ratios of 2.17 for iNaturalist (bobcat 2.81, deer 2.04,
coyote 1.67) against 0.98 for cameras. So any urban-rural difference in trend
produces a difference between the two streams' national estimates from
sampling composition alone, with neither stream biased. The axis is
load-bearing for interpreting every national trend.

**Use one estimator: the pooled continuous gradient on standardised
`Human_pop`, with cells as a random effect** (random intercept AND random
year-slope -- a random intercept alone still lets one cell drive the slope).
Report it per stream with intervals, plus a leave-top-ten-cells-out
concentration check.

Do NOT use these, both of which failed on real data:

- **Tertile contrast** -- discards the middle third and dilutes
  tail-carried gradients. It returned -0.6 for coyote where the signal was
  real and confined to the most urban cells.
- **Per-cell slopes, precision-weighted** -- drops cells below a detection
  threshold and fights the deployment weighting. It returned +3.8 for coyote,
  which did not reproduce, and +1.6 for bobcat where pooling gave +13.8.

An eightfold disagreement between estimators is a weighting and
cell-inclusion artifact, not noise. If two estimators disagree, run the
concentration check before believing either.

**Convert the gradient to an urban-rural trend difference before believing
it.** The screen reports percentage points of %/yr per +1 standardised unit of
`Human_pop`, which is opaque. Multiply by the actual urban-minus-rural spread
in that covariate -- measured at 0.44 to 0.68 units (median 0.58) across
species for camera cells, or 0.22 for a 1-SD framing -- to get the implied
difference in annual trend. A camera gradient of -46 becomes a 10 to 27
percentage-point-per-year difference between urban and rural places, which
compounded over a 16-year camera record is a 80-99% relative decline. Treat
any implied difference beyond roughly 5 points per year as implausible as
ecology and presumptively an artifact until the project check clears it.

**Small-bodied species are the most artifact-prone on the camera side.**
Detection of chipmunks, squirrels and similar small mammals is acutely
sensitive to camera height, trigger speed and detection-zone geometry --
precisely what changes when one project's cameras replace another's. Three of
the four species the screen first flagged are small rodents. Treat a
small-mammal camera gradient as unproven until the project fixed effect is
run, whatever its interval says.

**Why the random year-slope is not optional: camera-network composition.**
A pooled contrast with no cell or project term reads a changing *mix* of
cells across years as a trend. The cells that do the damage are
high-deployment, near-zero-detection ones -- bobcat's top three urban cells
carried 717 deployments with 7 detections, 571 with 0, and 558 with 1, each
spanning a decade and 8-22 separate projects. As those cells enter and leave
the pooled sample year by year, the fitted slope moves. This is also why
leave-ONE-cell-out is not a sufficient check: dropping any single cell left
bobcat's estimate at +12.1 to +13.9, while dropping the top ten together took
it to +2.5. Always run the random-year-slope fit and the leave-top-N-together
drop, not single-cell drops.

Related: only 22 of bobcat's 51 camera projects span two or more years, so
most deployments carry no within-project information at all. Report that
count whenever a project fixed effect is used -- a wide interval there may
mean the design cannot identify the effect rather than that the effect is
absent.

**Expect the camera arm to be the binding constraint.** Across the 15 fleet
species screened at national level, the camera interval is 3 to 23 times wider
than the iNaturalist interval for the same gradient (median 6x), and only 3
species -- eastern chipmunk, eastern fox squirrel, mule deer -- yield an
assessed verdict. Twelve are "not assessed, comparison underpowered" and one
lacks data. So the default screen outcome is NOT agreement; it is that the
comparison cannot be made. Read the `agreement` column rather than inferring
from whether each gradient excludes zero, and never report an underpowered
camera arm as corroboration or as contradiction.

**Confounds to test, not assume:**

- **Project turnover.** Refit the camera trend with project as a fixed
  effect. A rise surviving within projects is ecology; one that does not is
  camera-network turnover. Count how many projects span two or more years --
  only those identify a within-project trend.
- **Year coverage.** Check that urban and rural groups span comparable years.
  If urban deployments are mostly recent, the contrast is confounded with
  deployment timing and must be reported as such.

**What a cross-species pattern can and cannot rule out.** iNaturalist effort
is total mammal records per cell, so it reshapes IDENTICALLY for every
species (measured: a 5.4-point urban-rural differential for bobcat and deer
against 5.3 for coyote). A species with ample data showing no gradient is
therefore a negative control against **effort mis-correction**. It is NOT a
control against species-specific reporting behaviour, which is selective by
definition -- only the camera side can test that.

## 4. Model extension, when the screen flags a species

A post-hoc screen cannot propagate uncertainty or let the streams disagree
properly. Put the interaction in the model, reusing the existing
shared-parameter/sink architecture:

```r
# camera occupancy submodel
cloglog(psi[i]) <- ... + (year_beta + year_pop * Human_pop[cell[i]]) * year_occ[i]

# iNat intensity: shared gradient plus its own sink
total_var_beta <- year_beta + year_var
total_pop_beta <- year_pop  + year_pop_var
```

`year_pop` is shared, so camera-identified -- the gold-standard urbanisation
gradient. `year_pop_var` is the iNaturalist-only sink.

**The sink is not optional**, because in every species screened so far the
two streams disagree about the gradient rather than sharing it. Four species
(eastern chipmunk, eastern fox squirrel, eastern gray squirrel, mule deer)
have camera gradients of -14 to -46 with iNaturalist gradients near zero;
coyote and American black bear have the reverse, iNaturalist gradients
excluding zero with camera gradients that do not. A single shared gradient
would force agreement in both directions and return a compromise wrong for
each stream.

Do NOT use bobcat's +9.5-versus--5.7 urban camera figures as motivation --
they came from a pooled contrast and are withdrawn (see section 5).

The payoff: the decision rule in section 2 becomes ONE parameter with a
posterior. `year_pop_var` against zero *is* "do the streams agree about
urbanisation" -- no estimator choice, no tertile cut, no comparing separately
bootstrapped point estimates.

**A linear interaction is adequate even for a tail-concentrated effect**,
because standardised `Human_pop` is strongly right-skewed (skew 7.7; median
-0.27, 90th percentile +0.01, maximum +4.53). The top cell therefore carries
roughly 17 times the median cell's leverage, so a linear term already
weights the urban tail heavily -- which is why the continuous gradient
detected coyote's tail effect where the tertile contrast did not. Do not
replace it with a post-hoc decile indicator chosen from the same data.

**Use baseline-year population**, not contemporaneous. `Human_pop` is
time-varying in the bundles (it changes in 85-92% of rows), so a naive
`year x Human_pop` conflates "trend differs by how urban a place was" with
"trend differs by how urban it became". Fix the covariate at its first-year
value so the gradient means the former.

**Test on three species before any fleet commitment**, and do not bundle this
with other model changes -- if two things change at once, neither effect is
attributable.

## 5. What this workflow has found

Kept as calibration for what the screen is capable of detecting.

- **Bobcat**: a pooled contrast gave an urban camera increase of +13.8 points
  (urban +9.5%/yr against rural -4.3%/yr). **It did not survive and is
  withdrawn.** With cell random intercept AND random year-slope it is
  +2.7 [-7.8, +14.2]; dropping the top ten urban cells gives +2.5; with
  project as a fixed effect, +7.3 [-5.2, +16.7]. The rural -4.3 was equally
  fragile -- it becomes +0.2 once cell slopes are free. Within cells, bobcat
  camera trends are flat in both urban and rural places, and there is **no
  evidence of an urbanisation-by-year interaction.** Bobcat's camera/iNat
  divergence (+1.0 against -3.4%/yr under the union mask) remains unexplained.
- **Coyote**: a genuine iNaturalist-side gradient confined to the most urban
  cells. +4.8 [+0.4, +7.8] continuously within Eastern Temperate Forests,
  collapsing to -8.2 [-37.6, +21.4] with the top decile removed; by tertile
  it is +0.3, which is why the tertile estimator is excluded. The top decile
  holds 55% of that region's coyote iNaturalist records in 12% of its cells.
  **The camera comparison is NOT ASSESSED, not negative** -- the screen's own
  verdict for coyote at both national and regional level. The camera interval
  is 17.9 points wide against the iNaturalist arm's 5.1, so it could not have
  detected this gradient had it been there. An earlier version of this section
  said the camera side 'shows no tail effect, so this is iNaturalist-only';
  that was the exact error section 2 warns against, reading a wide interval as
  evidence of absence.
- **White-tailed deer**: urban cameras appeared to fall relative to rural
  (-4.1 points), but that is a pooled estimate and is **provisional** until
  rerun with cell random slopes.
- **Camera power is regional.** In practice only Eastern Temperate Forests
  has enough camera data for a regional contrast; every other region returns
  +-15 to 90 points. Report those as not assessed.
