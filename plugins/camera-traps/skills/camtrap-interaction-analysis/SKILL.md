---
name: camtrap-interaction-analysis
description: "Test for reactive species interactions in camera-trap detection data — does species B change its visitation rate in the hours or days after species A passes the same camera — using recurrent-event PAMM (piece-wise exponential additive mixed models) and/or the multivariate Hawkes process. Encodes the artifact diagnostics that must run BEFORE any smooth is interpreted (waiting-time support, diel composition of the lag axis, within-species burstiness), the nested model set that separates camera heterogeneity, self-excitation and time of day from the cross-species term, and the whole-day circular-shift permutation null that decides whether a fitted curve is biology or structure. Use for predator-prey avoidance, temporal co-occurrence, attraction/repulsion, or reproducing Ferry et al. 2024 / Nicvert et al. 2024 on a new array. Triggers: PAMM, ctrecurrent, pammtools, Hawkes process, UnitEvents, time-to-first-event, proximate co-occurrence, reactive avoidance, interaction function, artifact ratio."
metadata:
  authored_via: "claude-science"
  published_by: "agent"
  published_at: "2026-09-12T20:21:34.611Z"
  authored_by: "agent"
  authored_at: "2026-09-12T19:05:08.533Z"
  authoring_session: "472eb3bb-51df-4c72-9089-5f4f7d81736a"
  last_modified_by: "agent"
  last_modified_at: "2026-09-12T20:20:28.193Z"
---

# Camera-trap species interaction analysis

Fits and — more importantly — **falsifies** reactive interaction estimates from
camera-trap detection streams. The methods are easy to fit and easy to
over-read: a declining hazard curve after a predator detection is the default
output of these data even when no interaction exists. This skill is mostly about
not being fooled by that.

Pairs with `camera-trap-qc` (run that first) and `mdd-taxonomy` (if pooling
species into guilds).

## The one-paragraph version

Build the event stream, run the three model-free diagnostics in §2, fit the
nested model set in §3, then run the circular-shift null in §4. **The null is
the result.** A lag smooth with p < 0.05 that the null reproduces is not a
finding; a flat smooth whose null band is much narrower is a real bound. Report
the artifact ratio for every pair you fit, including the ones that came out
null.

## §1 Preconditions

Run `camera-trap-qc` first. Beyond it, three traps specific to this analysis:

**1.1 Timestamp zone.** `readr::read_csv` / `pandas.read_csv` will happily type
a timestamp column as datetime and label it UTC when the values are local
wall-clock readings. *Converting* rather than *relabelling* slides every stamp
by the zone offset. On a nocturnal-predator / diurnal-prey question this
manufactures or erases the entire signal. Read timestamp columns as
**character**, then attach the zone.

**1.2 Timestamp format is chosen for the whole vector.** `as.POSIXct(x)` picks
one format by trial against the vector. A handful of rows carrying a date with
**no time** is enough to make it fall back to `"%Y-%m-%d"` and silently discard
the time of day from *every* row. Always pass an explicit `format=`. Then
decide what to do with the time-less rows: **exclude them**, never admit them as
midnight — midnight rows read as night detections and bias the diel term.
Check the deployment table too; date-only start/end stamps also truncate effort.

**1.3 Deployment-level tables must be built by left join FROM the deployment
table**, never by aggregating the detections. A camera with zero detections
disappears from a `group_by(detections)` summary — and that is precisely the
camera that needs flagging (a long deployment with no detections is a failed
camera, not a quiet site; drop it from the exposure denominator).

Also settle, and state in the methods: whether co-located or near-duplicate
stations are one station or two (check for shared timestamps — genuinely
separate cameras share almost none), and whether the observations table has a
sequence id / group size at all. Without one you cannot verify the upstream
independence filter; say so rather than assuming a 30-minute rule.

## §2 Diagnose before you model

These three are model-free properties of the event times. Compute them first;
they frequently explain the whole result.

**2.1 Waiting-time support.** For each driver event, time to the next response
event at that camera, **with administrative censoring at the deployment end**
(an interval that never closed because the camera stopped is not evidence of a
long wait). Then tabulate how many intervals are still open at each lag. With
abundant prey and a rare predator the median wait is often under a day, so a
curve plotted to 7 days has almost nothing behind its right-hand half — and
what remains is a biased subset, because busy cameras close their intervals
within hours. **Truncate the fitted lag range to where the intervals live** and
report the support table.

**2.2 Diel composition of the lag axis.** The lag axis is not diel-neutral. If
the driver is nocturnal, short lags are disproportionately night; if the
response is diurnal, its rate there is low for reasons that have nothing to do
with the driver. Tabulate night share and crude response rate per lag bin, then
recompute the rate using **daylight bins only**. If the short-lag dip shrinks,
you have measured the confound directly. This single table is usually the most
persuasive object in the write-up.

**2.3 Within-species burstiness.** Share of short same-species intervals
against a Poisson process fitted at **each camera's own rate** (per-camera, so
between-camera rate heterogeneity is not the explanation). Ratios of 3-15x at
sub-hour gaps are normal — animals linger, backtrack, travel in groups, re-use
trails. This matters because a model with no term for a species' own bursts
must attribute them somewhere, and the cross-species lag smooth is the only
candidate on offer.

## §3 The PAMM model set

Frame it as a recurrent event problem (Ferry et al. 2024): hazard of the
response species as a smooth function of time since the driver's most recent
detection, using every occurrence rather than only the first.

Construct the piece-wise exponential data directly on a regular clock-time grid
(1-h bins work well) rather than fighting `pammtools::as_ped` for a covariate
that resets: per (camera, bin) record the response count, `log(bin length)` as
offset, and elapsed time since the driver's last detection and since the
response's **own** last detection, both evaluated at the **bin midpoint** so no
bin uses information from its own interior. Keep bins uniform in clock time —
that is what keeps exposure constant and the offset valid. Fit with
`mgcv::bam(family = poisson(), discrete = TRUE)`.

Fit the set **nested**, so each step removes one named explanation:

| model | adds | tests |
|---|---|---|
| M0 | driver-lag smooth only | reproduces the naive specification |
| M1 | `s(camera, bs="re")` | detection-level heterogeneity between cameras |
| M2 | `s(time since response's own last event)` | the response species' self-excitation |
| M3 | `s(tod, bs="cc")` | the diel confound from §2.2 |
| M4 | M3 on the truncated lag range | the support problem from §2.1 |

Read **curve shape and edf**, not just AIC — a term can improve fit while
leaving the artifact shape intact if it absorbs level rather than dynamics. An
edf driven to 1.00 means the smooth has been penalised to a straight line: no
lag structure remains to estimate. Report deviance explained at each step; the
progression is the finding ("all explainable structure is camera + self + time
of day, none is time-since-driver").

Handle the self-term's undefined region explicitly: before the response
species' first detection there is no "own last event". Keep those bins with an
indicator (`by=` a 0/1 seen-yet flag) rather than dropping them.

## §4 The circular-shift null — the arbiter

A term that fails a significance test can still be reported as a trend from its
fitted curve. So ask the different question: **is the observed curve
distinguishable from one fitted to data with no cross-species timing in it?**

Within each camera, shift the driver species' detections by a random **whole
number of days** and wrap inside the deployment window. Shift the **day index**,
not the raw elapsed time: deployment spans are not whole numbers of days, so
wrapping on elapsed seconds breaks the time-of-day preservation that makes the
test informative. Verify preservation with an assertion — the shifted
time-of-day multiset must be **identical** to the original.

This preserves the driver's rate, its exact time-of-day distribution, its
within-day burst structure, camera-level heterogeneity in both species, and the
response process untouched. It destroys only the between-species alignment.

Refit the **full** model (the one inference would rest on) per replicate, 199
replicates. Effect size: **range of the fitted driver smooth on the log-hazard
scale**, computed identically for observed and null.

- `artifact_ratio = median(null range) / observed range`. At or above 1 the null
  reproduces the observed curve — uninterpretable regardless of how clean it
  looks.
- `p_vs_null = (1 + #{null >= observed}) / (1 + n_rep)`.
- Also report **what fraction of null replicates returned a nominally
  significant lag smooth**. Near 5% means the test is calibrated; far above
  means the model is anticonservative and *no* p-value from it is usable. This
  check is what separates "no effect" from "no power".

### §4.1 WHICH invariants the null preserves decides the answer

This is not a detail. Two nulls that both preserve per-unit detection rate and
per-species time-of-day can give **opposite answers on identical data**,
because one also preserves within-day clustering and the other does not.

Demonstrated case (Swinkels et al. 2023's null vs this skill's null, on one
camera dataset, same observed statistic, 199 replicates each):

| null | what it does | ocelot sub-hour gap share | p |
|---|---|---|---|
| shuffle each detection's DATE within a unit, keep its time-of-day + species | destroys bursts | 0.043 -> 0.010 | **0.005 "avoidance"** |
| shift the driver's DAY INDEX, keep the within-day offset | preserves bursts exactly | 0.043 -> 0.043 | 0.49 (nothing) |

The mechanism is general and has nothing to do with predators: **bursty
arrivals lengthen typical waiting times at a fixed rate**, because events pile
into bursts and leave long empty stretches between them. A null that removes
burstiness therefore produces shorter waits than the real data, and the real
interval reads as avoidance. Any date-shuffle, day-randomisation or
"resample-within-season" null has this property. Camera-trap detections are
strongly bursty in every species measured so far (2-12x the Poisson share of
sub-hour gaps), so the artifact is available in essentially any dataset.

**Requirements that follow.**

- Shift **whole days**, keeping the within-day offset, whenever you want
  time-of-day AND clustering preserved together. Shifting the day index is not
  interchangeable with wrapping on elapsed time - spans are not whole numbers
  of days.
- **Publish a table of the invariants your null preserves**, not a prose
  description of the shuffle: per-unit rate, per-species diel profile,
  within-day clustering (share of sub-hour same-species gaps is a fine
  summary), between-unit heterogeneity, seasonal trend. Reviewers cannot
  otherwise tell which null you built, and neither can you.
- Verify the invariants with **assertions**, not by inspection: the shifted
  time-of-day multiset must be *identical*, and the burst share must match to
  the printed precision.
- When contradicting or replicating an earlier study, **re-run its null and
  yours against the same observed statistic on the same data**. That localises
  the disagreement to the null rather than to the system, which is a far
  stronger and more collegial claim than a bare difference in results.
  `R/10_null_comparison.R` in this skill does exactly this and is reusable.

## §5 The multivariate Hawkes process

Intensity = constant background rate per species + summed contributions of all
earlier detections of every species, each weighted by a piece-wise constant
interaction function on K bins of width delta. Coefficients may be **negative**,
so avoidance is expressible.

**What it adds:** the self-interaction function is estimated **separately** from
the cross-interaction functions, structurally. In the PAMM that separation has
to be bolted on (M2). So a Hawkes fit is a genuinely independent check on
whether burstiness was contaminating the cross-species estimate — not a
re-derivation of the same term.

**What it cannot do:** the background rate is a single **constant** per species.
There is **no time-of-day term anywhere in the model** — the original authors
flag this as future work. So it has strictly *less* machinery for the diel
problem than a PAMM's cyclic smooth, and it is the wrong tool to reach for as a
*fix* for a diel confound. Expect a 24-h echo in the self-interaction functions
(a peak in the first bin and a second at 18-30 h): that is the species' circadian
rhythm with nowhere else to go, and the original authors report it too.

**Carry the §4 null through the Hawkes fit.** Shift *every* species
independently by its own whole-day offset per camera. Whole-day shifts leave each
species' own inter-event structure untouched, so the **self** terms are
preserved by construction while the **cross** terms lose all alignment — giving a
null band for the cross terms while the self terms stay readable. Then test the
*count* of exceedances against the nominal rate (`binom.test(n_out, n_cross,
0.05)`); a 5% exceedance rate is no evidence of interaction, however many
individual coefficients look "significant".

**Implementation.** The reference implementation is `UnitEvents` (not on CRAN;
its host and the figshare mirror are frequently unreachable). If you must
re-implement the penalised least-squares estimator from the paper's equations:

- **Validate by parameter recovery before reporting any fit.** Simulate a
  known process (Ogata thinning) with a known self-excitation, a known
  attraction and a known repulsion; require correct signs on all non-zero
  terms, background rates within ~25%, and true zeros returned as zero.
  Make it a hard `stopifnot()` in the driver script, not an eyeball check.
  Expect negative terms to be **attenuated** by L1 shrinkage — read them as
  conservative.
- **Counting events strictly before an evaluation time needs a left-open
  interval search** (`findInterval(x, ts, left.open = TRUE)`). An epsilon
  offset (`x - 1e-9`) is below machine precision at Unix-timestamp magnitude
  (~1.7e9, where eps is ~4e-7), so it silently does nothing and **every event
  counts itself in its own first bin** — the self-excitation term then absorbs
  the entire event count. This failure passes unnoticed on small time origins
  and appears only on real timestamps, so validate on **POSIX-magnitude**
  simulated times.
- Drop the first `K * delta` of each deployment as burn-in (count windows
  there reach back before recording began).
- Jitter exactly simultaneous cross-species detections by up to a minute; the
  model disallows ties.
- Check sensitivity to delta (the published fit used delta=6 h, K=6; also run
  delta=3 h, K=12).

## §6 Interpretation limits to state, not bury

- **Driver rarity bounds a negative result.** Count cameras with zero and with
  1-3 driver detections. Effects attenuate toward zero under that measurement
  error, so a null is weak evidence of absence. State the count.
- **Station spacing bounds the question.** A response operating below
  inter-camera spacing (prey diverting tens of metres around a predator's route)
  is invisible to the array and would not be expected to appear. Say so.
- **Persistent spatial avoidance is a different claim** and a single array
  cannot separate it from shared habitat preference. Do not let a reactive null
  be read as a spatial one.
- The published Hawkes simulations suggest reliable detection needs interaction
  strengths >= 0.1/day with several hundred camera-days per camera; compare
  against your own budget before treating a Hawkes null as informative.

## §7 Reporting conventions

- Figures **numbered**, with titles that state the **result** so the figure
  reads without the main text, and a one-line take-home per panel as a subtitle.
- Never write jargon into a caption without unpacking it in the same caption:
  "at risk", "self-excitation", "clustering", "survives the null" all need a
  plain-language gloss — and for behavioural terms, give the *behavioural*
  reading (self-excitation = lingering, backtracking, group travel, trail re-use,
  return visitation), not just the statistical one.
- Emit a `key_numbers.txt` from the driver script containing every value quoted
  in the write-up, so prose is never typed from memory.
- Report the artifact ratio for **every** pair fitted, including nulls.

## §8 Reference implementation

`R/` in this skill bundles working modules from a completed analysis (two nested
grids, 50 deployments, 7 species):

| file | reusable? |
|---|---|
| `R/02_pamm.R` | generic — PED construction + nested model set |
| `R/03_null.R` | generic — day-index circular shift + artifact ratio |
| `R/05_hawkes.R` | generic — design, estimator, simulator, recovery validation, Hawkes null |
| `R/07_intervals.R` | generic — censored waiting-time tables, burstiness vs Poisson |

Adapt column names at the top; `build_ped`, `fit_pamm_set`, `null_test`,
`hawkes_with_null`, `hawkes_recovery_check`, `lag_table` and `burst_table` are
the entry points. Ingest and figure modules were dataset-specific and are not
bundled — write those per dataset following §1 and §7.

## References

- Ferry, N., S. Dray, C. Fritz & M. Valeix. 2024. Introducing recurrent event
  analyses to assess species interactions based on camera-trap data. *Methods in
  Ecology and Evolution* 15: 1244-1258. doi:10.1111/2041-210X.14338
- Nicvert, L., S. Donnet, M. Keith, et al. 2024. Using the multivariate Hawkes
  process to study interactions between multiple species from camera trap data.
  *Ecology* 105: e4237. doi:10.1002/ecy.4237
- Lambert, R.C., C. Tuleau-Malot, T. Bessaih, et al. 2018. Reconstructing the
  functional connectivity of multiple spike trains using Hawkes models.
  *Journal of Neuroscience Methods* 297: 9-21.
