---
name: biologging-acc-imu
description: "Work with animal-borne accelerometer, magnetometer and gyroscope (IMU) data: retrieving acceleration bursts from Movebank, parsing compact vs expanded burst formats, calibrating raw ADC counts to physical units, computing VeDBA and ODBA, classifying active vs resting, and building diel activity budgets. Covers the R move2imu / tagtools / rabc stack and the Python pyecoacc / stickleback tools. Use for biologging ACC or IMU data, ODBA or VeDBA, activity budgets or proportion of time active from collars, behaviour classification from accelerometry, or burst-structured sensor data."
metadata:
  authored_via: "claude-science"
  published_by: "agent"
  published_at: "2026-09-17T13:38:10.271Z"
  authored_by: "agent"
  authored_at: "2026-09-17T01:55:20.298Z"
  authoring_session: "e8ae01ce-d9c1-4c48-9d91-22908a03cf70"
  last_modified_by: "agent"
  last_modified_at: "2026-09-17T13:37:43.796Z"
---

# Biologging accelerometer and IMU data

Animal-borne tags record inertial data (accelerometer, magnetometer, gyroscope)
in **bursts**: short runs of fixed-frequency samples, separated by long gaps,
because continuous recording is too costly in battery and storage. Almost every
mistake in this area comes from treating burst-structured data as if it were a
regular time series, or from comparing values across tags that were never on the
same scale.

## Decide what you are estimating first

Three questions get confused, and they need different pipelines:

| Question | What you need | Pitfall |
|---|---|---|
| What behaviour is this animal doing? | Supervised classifier trained on observed labels | Needs ground-truth video/observation; accuracy claims inflated by class imbalance |
| How hard is it working? | VeDBA magnitude | **Not comparable across tags** without calibration and identical placement |
| What fraction of time is it active? | Two-state split of an activity metric, per individual | Threshold choice, and sampling effort that varies with time of day |

## The scale-free rule

The single most important design constraint when pooling across tags, settings
or studies: **any metric formed as a ratio of two quantities from the same
series is invariant to a constant gain on that series; anything reported in
units of g is not.** Tag placement, attachment tightness, generation and
calibration all multiply the magnitude.

Practical ordering, robust to least robust:

1. **Ratios and timings** — nocturnality index, active-time fraction, hour of
   peak activity, diel concentration, response slopes (activity regressed on a
   covariate). Essentially invariant.
2. **Bout structure** — bout length, frequency, fragmentation. Usable, but
   *only* if defined on a smoothed series with an explicit minimum episode
   duration, and the smoothing window set by the **coarsest** sampling regime in
   the pool, not the finest. Otherwise the metric measures the tag's sampling
   rate.
3. **Absolute magnitude** — mean VeDBA, daily VeDBA sum, energy expenditure.
   Do not pool these across heterogeneous tags. Energetics additionally needs a
   species-specific acceleration-to-oxygen-consumption calibration, which exists
   for few species; treat it as a calibration project, not a first deliverable.

**Fit one threshold per species, not per individual — but verify the mode
separation first.** Pooling all of a species' animals and fitting a single
two-component mixture to the log metric gives a threshold that is reportable,
transferable to a new animal without refitting, and reproducible by someone else.
Measured on 520,309 collar bursts from 96 animals across 7 species, a
species-level threshold agreed with per-animal thresholds on **96.9%** of bursts,
moved the proportion active at the daily peak by at most 0.030, and left the
ranking of species unchanged. No animal was driven to an extreme fraction active.

The reason a pooled threshold survives is that the two modes are far apart:
standardised separations of 3.4 to 6.4 in that dataset, so almost no records sit
near the boundary even though the per-animal boundaries themselves span a factor
of 2 to 10 within a species. **Check that separation before pooling.** Where it
is small, per-animal fitting is the fallback, and a species-level cut genuinely
would assign whole animals to one state.

Do **not** normalise each animal by its own median and then apply a species-level
multiplier. It sounds like the scale-free fix and it performs worse — the median
sits at a different position relative to the two modes depending on the animal's
duty cycle, so the normalisation injects the very between-animal variation it is
meant to remove. In the same test it shifted one species' peak by 0.17.

## Tool landscape

**R, IMU data handling** — `move2imu` (Kranstauber & Roberts). Unified vector
representation of acceleration/magnetometer/gyroscope bursts, Movebank-native,
integrates with `move2`. Handles the compact/expanded format split transparently
and carries per-tag calibration. Not yet on CRAN:
`pak::pak("move2universe/move2imu")`. This is the right substrate for
Movebank-sourced collar data.

**R, high-resolution tags** — `tagtools` (animaltags project, CRAN; also
Matlab/Octave, partial Python). Built for DTAG-class tags sampling many times
per second with accelerometer, magnetometer, pressure and sometimes gyroscope
and sound. Provides calibration to scientific units, multi-panel visualisation,
derived metrics including jerk and dynamic acceleration, dive detection, track
reconstruction, a rotation test and Mahalanobis-distance analysis. Uses NetCDF
plus standard metadata structures.

**R, supervised behaviour classification** — `rabc` (Yu & Klaassen 2021,
doi:10.1002/ece3.7937). XGBoost on windowed time- and frequency-domain features,
with interactive visualisation, feature selection and UMAP embedding of the
labelled behaviours; deliberately not a one-click service, so the user chooses
the behaviour categories. `accelerateR` (Rast) covers the same pipeline shape.

**R, pre-trained ungulate models** — `AccelerometerBehavior` (Smiley et al.
2025, doi:10.1002/ece3.72722; github.com/STRankins/AccelerometerBehavior).
Field-validated three-state models for moose, bighorn sheep and mule deer from
Vectronic collar activity counts. Notable because it needs **no** training data
of your own, which is otherwise the binding constraint on supervised work.

**Python, supervised behaviour classification** — `pyecoacc` (Resheff et al.
2026, doi:10.1111/2041-210x.70261). Standard accelerometer feature computations
plus both traditional and deep-learning pipelines. The Python counterpart to
`rabc`; same lineage as the older web tool AcceleRater.

**Python, behavioural events** — `stickleback` (PyPI; R interface
`rstickleback`). Time-series classification for brief events representable as a
point in time (feeding lunges, social interactions) rather than states.

**Marine / diving** — `diveMove` for dive phases and depth/speed calibration;
`rbl` for prey-catch attempts and swimming effort from accelerometry.

## The burst data model

Two storage layouts, and the distinction matters:

- **Compact** — one burst per row. Values in a single space-delimited string;
  frequency and axes in separate metadata columns. Burst boundaries are explicit.
- **Expanded** — one sample per row, each with its own timestamp. Frequency and
  burst boundaries must be **inferred** from the interval sequence.

In expanded data the frequency is not recorded, so it is inferred from the gaps
between consecutive samples: a run of identical intervals becomes one burst, and
any change in interval starts a new one. The consequence is that **a change in
sampling frequency and noise in the recorded timestamps are indistinguishable** —
both look like an interval change. A single late timestamp splits one burst into
three.

`move2imu` exposes three controls for this, and all three have failure modes in
both directions:

- `freq_tol` — relative tolerance around the running frequency, so small
  deviations don't start a new burst. Keep it as small as will absorb your
  actual jitter. At large values it *blends* genuinely different frequencies,
  spreading the gap between two bursts across all samples and producing a
  completely spurious frequency.
- `gap_tol` — allows adjacent bursts of the same frequency separated by a tiny
  gap to merge. Needed because tags with a maximum payload size report
  *continuous* recording as a sequence of nominally separate bursts. Diagnostic:
  burst intervals clustering near zero, and burst durations nearly equal to the
  inter-burst interval. Note that merging **recalculates** the frequency from
  the new sample count and elapsed span, so it will differ slightly from the
  recorded frequency; overriding it back makes the bursts untrue to the recorded
  timestamps. Pick which you want deliberately.
- `min_freq` — splits off single samples recorded alongside GPS fixes, which
  some tags report as IMU data at a far slower rate. Single-sample bursts always
  have `NA` frequency, since one sample implies no interval.

Before any of this, data must be **sorted by timestamp within track and
deduplicated**, or burst identification fails outright
(`move2::mt_filter_unique()`).

## Retrieving acceleration from Movebank

Specifics that are easy to lose an hour to (direct-read REST API):

- Sensor is identified by **numeric id**: GPS `653`, acceleration `2365683`.
  A sensor name string silently returns a header row and nothing else.
- The **default attribute set omits the acceleration values.** Request
  `attributes=all` once on a short window to discover the real column names,
  then name them explicitly. For e-obs tags the payload is
  `eobs_accelerations_raw` (space-separated integers, interleaved x y z x y z),
  with `eobs_acceleration_axes` and
  `eobs_acceleration_sampling_frequency_per_axis`.
- **Acceleration records carry no coordinates.** For anything needing position
  (solar time, habitat), join to GPS — the animal's median location is
  sufficient for solar calculations, since sunrise varies by under a minute
  across a home range.
- A request for the whole study attribute set can hang or rate-limit (HTTP 429).
  Narrow the attribute list and **chunk by time**; acceleration is large enough
  (order 50 MB per collar-day for a 20-animal deployment) that you should reduce
  each chunk to per-burst summaries and discard the raw payload before moving on.
- Some payload strings are truncated or malformed. `numpy.fromstring` raises and
  discards the prefix it parsed, killing the whole chunk; parse tolerantly so one
  bad burst costs that burst only.
- Studies other than your own return an **HTML licence-acceptance document**
  instead of data. Do not auto-accept licences on a user's behalf — report which
  studies are gated and let them decide.

For estimating a proportion active, you rarely need every day. Sample days
spread evenly across the deployment so all hours and seasons are covered, and
reduce as you go.

## Calibration

Raw ADC integers have no physical units. The transformation is linear — an
offset (the ADC value corresponding to zero) and a slope (output increment per
ADC increment) — plus an **axis orientation** indicator, because manufacturers
disagree on which direction each axis points.

Two traps:

1. **Assigning units is not converting.** `set_imu_units()` labels the values;
   `transform_imu()` converts them. Calling the former on raw counts gives you
   values in the thousands wearing a unit of g.
2. **Calibration differs by tag generation**, not just manufacturer — e-obs has
   revised its defaults over time. A study spanning generations needs a
   *vectorised* per-burst calibration built from tag id, not one study-wide
   constant. Sanity check: raw acceleration in the thousands means ADC counts;
   values near 1 g on the gravity axis mean converted.

`move2imu` ships defaults for e-obs and Ornitela; for others supply offset and
slope yourself, optionally per axis, and keep them in an external file rather
than inline. User-supplied values override manufacturer defaults, which is also
how you re-orient one manufacturer's axes to match another's.

## Computing an activity metric

**VeDBA** is the default activity metric: the Euclidean norm of the three
dynamic (static-removed) acceleration components, averaged over the burst's
samples. **ODBA**, the sum of the three absolute components, is the older
alternative and appears widely in the literature, but report VeDBA unless a
specific comparison demands otherwise, for two reasons: it is the more commonly
reported of the two now, and it is **rotation-invariant** — an L2 norm does not
change if the tag sits at a different angle on the collar, whereas an L1 sum
does, because it depends on how a given acceleration vector is distributed
across the axes.

The static (gravitational) component is estimated as a running mean,
conventionally over about one second. Where a burst is shorter than that window
the running mean degenerates to the burst mean, which still removes the gravity
offset — the common case for short collar bursts.

**Switching between them rarely changes a classification.** For a single
acceleration vector the two are bounded by VeDBA <= ODBA <= sqrt(3) x VeDBA, so on
one tag they are near-perfectly monotonically related. Measured on 26,821 fisher
collar bursts: Spearman correlation 0.998, ratio tightly concentrated (median
1.49, 5th-95th percentile 1.44-1.54), and a two-state classification built on
each agreed on **99.8%** of bursts, with the 0.18% of disagreements sitting
within one percentile of the threshold. Expect a VeDBA threshold around two
thirds of the corresponding ODBA one. So prefer VeDBA on convention and
orientation-invariance, not in expectation of different answers — and if you are
revisiting an ODBA analysis, do not expect the switch alone to resolve a
discrepancy.

`burst_metrics()` in this skill's kernel returns both from a Movebank-style
interleaved payload; `bursts_to_metrics()` maps it over a frame.
`classify_two_state()` fits a two-component Gaussian mixture to the **log**
metric and labels the lower-mean component resting. Check the fitted separation
between component means before trusting it: well-separated collar data gives a
standardised gap above about 3, and a gap below 1 means the two states are not
resolved.

## Linking acceleration to position

Acceleration rows carry **no geometry** — the tag's locations live in the GPS
rows of the same object. Three cases, in order of how much care they need:

1. **Simultaneous records.** Where the tag writes an acceleration burst and a
   GPS fix at the same timestamp, join on track id and timestamp directly.
2. **Offset records.** More often the GPS fix lands just after the burst start,
   so an exact join returns nothing. Use a rolling join to the nearest or the
   most recent *preceding* burst, and **group by individual** so records are
   never linked across animals.
3. **Independent schedules.** Where the two sensors run on unrelated schedules,
   interpolate positions to the acceleration timestamps rather than joining.

Where position is only needed for something that varies slowly in space — solar
time, broad habitat — the animal's median location is enough and avoids the join
entirely.

## Within-burst variation and rolling summaries

Collapsing a burst to one number treats it as a snapshot, which is reasonable for
short bursts but discards real structure in longer ones. Two refinements:

- **Rolling window inside the burst.** Reconstruct per-sample timestamps from the
  burst start, frequency and sample count, then compute the activity metric over a
  sliding window (about a second) within the burst. Dynamic acceleration can vary
  substantially around the whole-burst value. The standard deviation of those
  rolling values is a useful per-burst summary of variability in its own right,
  and is scale-free in the same sense as other ratios only if you express it
  relative to the burst mean.
- **Time-aware rolling average across bursts.** For questions about sustained
  inactivity — tag failure, mortality, injury — average the metric over hours of
  elapsed time, not over a fixed number of bursts, so an irregular burst schedule
  doesn't change the window length. Flag when the rolling mean stays below a
  threshold for a set duration. Both the threshold and the duration are
  species- and tag-specific and have to be set from the data at hand; there is no
  transferable default. Because each animal is compared only to its own baseline,
  this class of within-individual anomaly detection needs no cross-study
  harmonisation, which makes it the lowest-barrier use of a heterogeneous archive.

## Sampling effort is the trap in diel work

Tags duty-cycle. Recording density can differ several-fold between day and night,
and can change mid-study.

- Within-hour ratios are **safe**: the proportion active among samples in an hour
  is unbiased regardless of how many samples that hour got, provided the hour is
  not empty. Check for empty bins before taking a maximum.
- Anything summed over time is **not** safe: daily VeDBA totals, counts of active
  samples, and any count model over time bins need an explicit per-bin effort
  offset.
- `plot_sampling_effort()` in `move2imu` shows where tags started, stopped and
  changed regime. Look at it before modelling, not after.
- **GPS and acceleration have different effort profiles on the same collar**, and
  GPS fix success itself depends on behaviour and cover. A movement-derived active
  fraction at a several-minute fix interval also counts the whole interval active
  if the animal moved at all within it, so it runs high relative to an
  instantaneous accelerometer classification. Where both channels exist, compare
  them; disagreement in the *timing* of the peak points at effort or fix-success
  bias rather than at biology.
- If a diel curve is expressed in sun-anchored time, the mapping must be built
  from **continuous timestamps against actual sunrise/sunset instants**, not from
  hour-of-date. Where sunset falls after midnight UTC the naive version silently
  throws real daytime samples into the night branch and leaves hard zeros in the
  middle of the curve. Verify anchors land exactly: sunrise at 0, solar noon at 6,
  sunset at 12, solar midnight at 18.

## Reporting

Sample size for accelerometry is **animals, not bursts**. A million bursts from
five collars is five replicates. Bootstrap over individuals, and where a metric
is a maximum over time bins, note that the maximum of a noisy curve is biased
upward — fix the peak location from the full data and interval the value there,
rather than re-selecting the argmax in each bootstrap replicate.

## Not covered here

Supervised classifier training and validation (use `rabc` or `pyecoacc` and
their own guidance); magnetometer-based dead reckoning and heading analysis;
absolute energetics calibration; marine dive analysis.
