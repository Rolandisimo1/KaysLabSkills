---
name: integrated-data-stream-models
description: "Combining two or more data streams with different observation processes into one model: which parameter is the reportable estimate, how to test whether the streams describe the same underlying surface, and how to report what each stream contributed. Load BEFORE building any figure, map, table or report section from an integrated or data-fusion model -- including abundance or intensity surfaces, change maps, covariate effects, and any comparison between streams -- not only when writing conclusions. Use for integrated species distribution models, presence-only plus presence-absence fusion, structured survey plus opportunistic or citizen-science data, sensor plus survey fusion, and any joint likelihood where one stream has measured effort and another does not. Also use when deciding whether a pattern is real or an observation artifact, and when interpreting coupling or scaling parameters linking one stream's intensity to another's."
---

# Integrated models over multiple data streams

For any model that fits two or more streams to one shared latent surface
through separate observation models. The canonical case is a designed survey
with measured effort joined to an opportunistic stream with unmeasured effort,
but the same structure appears in sensor-plus-survey fusion, museum records
plus systematic transects, and presence-only plus presence-absence models.

The failure mode this skill exists to prevent is not a modelling error. It is
reporting a quantity from the wrong part of the model, or asserting that the
streams agree without using the statistic the model already provides.

## 0. Checklist, before any artifact leaves your hands

Run these four against anything that shows an estimate, a surface, a change
map, or a comparison between streams. The work usually looks like
figure-building rather than like inference, which is exactly why this gets
skipped.

1. **Name the quantity, in the artifact itself**, not only in the caption. An
   integrated model carries several latent and observed quantities, and they
   do not share a trend or a scale. A panel that does not say which one it
   shows will be read as the headline result.
2. **Quote the coupling parameter with its interval**, against both of its
   thresholds (section 2), before any sentence about whether the streams
   agree. If you are writing such a sentence and it does not contain the
   coupling estimate, you have reinvented a worse version of it.
3. **Say whether the single-stream control fit exists** (section 3). If it has
   not been run for the data in hand, say so in the artifact rather than
   leaving the comparison looking complete.
4. **Say whether the composition screen has been run** (section 4). Its
   default outcome is "not assessed", which is not the same as agreement.

If any of 2-4 is unavailable, publish a coverage table naming which checks
exist and which do not. A reader cannot distinguish a missing check from a
passed one, and will assume the latter.

## 1. Anchor the estimate to the stream whose effort is measured

Give each stream its own observation model over a shared latent surface, and
decide in advance which stream's parameter is the reportable one.

The stream with measured effort is the anchor: its non-detections are
informative, so it identifies the parameter. The opportunistic stream extends
spatial and temporal coverage and sharpens the surface, but it cannot carry
the headline estimate because its effort is unknown.

**The structural device that makes this work is a sink.** Give the
opportunistic stream its own additive increment on the parameter of interest:

    anchored      = beta              # what you report
    opportunistic = beta + beta_extra # what the second likelihood sees

`beta_extra` absorbs signal specific to the opportunistic stream -- changing
observer behaviour, growing platform adoption, a reporting campaign -- which
is what keeps `beta` identified by the anchor stream. **Report `beta`, never
the sum.** The sum is the opportunistic stream's estimate wearing the joint
model's authority.

These two can differ in sign. Check before assuming the choice is cosmetic.

**Convert to interpretable units before comparing anything.** Submodels
routinely standardise a shared covariate over different distributions, so
their raw coefficients are not on a common scale and the sum mixes two scales.

**A third quantity hides here.** A trend fitted to the opportunistic stream's
*expected counts* is the opportunistic parameter attenuated by the coupling
exponent, so it runs shallower than either coefficient and is a third number
again. Three quantities, three trends. Name which one any figure shows.

## 2. The coupling parameter is the primary agreement metric

Most integrated models link the streams through something of the form

    log(mu) = alpha + theta * log(lambda)

where `lambda` is the shared latent intensity and `mu` the opportunistic
stream's expected count. **`theta` is the model's own statement about whether
the streams describe the same spatial pattern.** Quote it with its interval
before any other agreement diagnostic.

It is an exponent, so read it as a multiplier: a location with twice the
latent intensity yields `2^theta` times the opportunistic records.

**There are TWO thresholds, and the healthy state is strictly between them.**

- **theta = 0 is the no-agreement value.** The expected count becomes constant
  across locations, so the records carry no spatial information about the
  latent surface at all. An interval including 0 means the stream cannot be
  shown to track the surface, and whatever it contributes is its own sampling
  pattern. Below zero is worse than useless: more records where there is less
  of the thing.
- **Interval strictly inside (0, 1)** -- partial correspondence. The
  opportunistic stream under-responds to real differences, which is the normal
  and healthy state. The anchored estimate is safe to report.
- **Interval reaching or exceeding 1** -- proportional or over-responding. No
  plausible observer behaviour produces over-response, so this is the
  signature of the opportunistic pattern tracking something other than the
  latent surface, with `theta` absorbing the distortion. Treat the joint
  estimate as unreportable until a single-stream control confirms it.

**Judge on the interval, never the mean.** A mean sitting mid-band with an
interval spanning both thresholds is uninformative, not healthy.

**Check that `theta` itself converged** before using it as a gate. A gate
verdict resting on a poorly mixed chain is not a verdict. Where `theta` and
the opportunistic increment are weakly identified, the likelihood often
constrains only their product, producing mirror-image modes of opposite sign
that fit equally well. Diagnose by computing the product per chain: if
opposite-sign groups agree on it, the two are jointly unidentified and
neither should be reported.

**Why this is the primary metric** rather than a correlation between the
streams' outputs: it has a mechanism, it comes with an interval, and it is
available from the joint fit alone, so it screens before any control fit
exists. It is a gate, not a dose-response -- it predicts *whether* a problem
exists better than *how large* it is.

## 3. The single-stream control fit tests whether it mattered

`theta` says whether the streams correspond. The control says whether
non-correspondence actually moved this estimate. Refit with the opportunistic
likelihood removed and compare:

- **Control resolves the same direction** -- the joint estimate is anchored.
  Report it, since it is the more precise of the two.
- **Control spans zero or flips sign** -- do not report the joint estimate.
  Report the control, or report the case as unresolved.

Report the per-stream estimates and their difference **with an interval**, not
two point estimates side by side. A wide difference interval is "not
assessed", not "no difference".

**Quantify what integration bought, and be willing to find it modest.** On a
34-species fleet, adding the opportunistic stream narrowed the anchored
interval by 14% and resolved no additional cases on net. Its value was in the
spatial and covariate surfaces and the longer window, not in the headline
estimate. That is a defensible and publishable finding; claiming more is not.

## 4. The composition screen

Streams rarely sample the same places in the same proportions. Where they
differ along an axis that also modifies the quantity of interest, the two
streams produce different national estimates from sampling composition alone,
with neither stream biased.

Identify the axis on which the streams' sampling differs most -- urbanisation,
accessibility, elevation, proximity to roads or population -- and screen every
case along it.

- Use **one** estimator: a pooled continuous gradient on the standardised
  covariate, with location as a random effect carrying **both** a random
  intercept and a random slope. An intercept alone lets a single location
  drive the slope.
- Do not discretise into tertiles or quantile contrasts. Discarding the middle
  dilutes tail-carried effects, and a real tail effect can vanish entirely.
- Do not use per-location slopes weighted by precision: it fights the design
  weighting and drops exactly the sparse locations the question is about.
- Run a **leave-top-N-together** concentration check, not leave-one-out.
  Dropping any single location often changes nothing while dropping the top
  ten changes everything.
- **Convert the gradient into the units of the question** before believing it.
  "Effect per standardised unit" is opaque; multiply by the actual spread
  between the groups you care about and sanity-check the implication.

**Expect "not assessed" to be the common outcome.** When the anchor stream's
interval is several times wider than the opportunistic stream's for the same
gradient, the comparison cannot be made. Never report an underpowered anchor
arm as corroboration or as contradiction.

**Composition turnover masquerades as trend.** When the set of sampled
locations changes across time, a pooled contrast with no location term reads
the changing mix as a temporal effect. High-effort, low-detection locations
entering and leaving the sample do the most damage.

## 5. When the screen flags something, put it in the model

A post-hoc screen cannot propagate uncertainty and cannot let the streams
disagree properly. Reuse the shared-parameter-plus-sink architecture: make the
gradient shared, so it is identified by the anchor stream, and give the
opportunistic stream its own increment on it.

    anchored gradient      = gamma
    opportunistic gradient = gamma + gamma_extra

**The sink is not optional.** If the streams disagree about the gradient
rather than sharing it, a single shared term forces agreement in both
directions and returns a compromise wrong for each.

The payoff is that the agreement decision becomes one parameter with a
posterior: `gamma_extra` against zero *is* "do the streams agree about this
axis", with no estimator choice and no comparing separately bootstrapped
points.

**Fix a time-varying covariate at its baseline value** when interacting it
with time, or the interaction conflates "the effect differs by how urban a
place was" with "differs by how urban it became".

**Test on a few cases before any fleet-wide commitment, and change one thing
at a time.** If two things change at once, neither effect is attributable.

## 6. Surfaces are not protected by the sink

The sink protects the *anchored parameter*. It protects nothing computed from
the opportunistic side.

Intensity surfaces, period-change maps and anything derived from the
opportunistic stream's expected counts move with the summed parameter, not the
anchored one. **They can therefore move opposite in direction to the headline
estimate for the same case** -- on one fleet, three of eleven species did,
and two of those three had a `theta` interval spanning zero, which is the
mechanism rather than a coincidence.

Print both numbers on any such panel and mark the disagreements.

**Recovering the latent surface.** Where the link is `log(mu) = alpha + theta *
log(lambda)`, the latent surface is recovered as `log(lambda) = log(mu)/theta`
up to an additive constant, which cancels from both the spatial pattern and
the change. Do not invert when `theta` is near zero: the division amplifies
without limit, and a `theta` interval spanning zero means there was no signal
to recover.

**Before showing a time sequence of surfaces, check that the shape changes.**
If the latent surface's rank correlation between first and last period is
above roughly 0.99, a per-period sequence is one picture repeated, and the
informative figure is one surface plus a change panel.

## 7. Worked instance

The camera-trap plus iNaturalist mammal-trend model is this structure with
`theta1` as the coupling exponent, `year_beta` anchored in the camera
occupancy submodel, and `year_var` as the sink. Project-specific thresholds,
fleet values and the history of what the screens have found live in the
`camera-inat-stream-agreement` skill. Load that one as well when working on
that project; this skill is the general method behind it.
