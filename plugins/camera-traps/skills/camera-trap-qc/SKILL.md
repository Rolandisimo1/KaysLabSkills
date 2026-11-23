---
name: camera-trap-qc
description: Quality-control checks and analysis conventions for multi-project camera trap data (Wildlife Insights, eMammal, Snapshot USA, Candid Critters exports) before diel-activity, occupancy, or detection-rate modelling. Catches timezone storage inconsistencies and per-camera clock faults, malformed camera array definitions, repeated-site sample-size inflation, cross-project name-substring and spatial pre-block pooling errors, sun-time effort bias, and shared-denominator artifacts in rate-vs-metric regressions. Requires timezonefinder for correct local-clock sunrise/sunset. Pairs with mdd-taxonomy for species-name resolution. Use when handed a deployments/sequences table, when combining camera trap projects, or when reviewing an activity-pattern analysis.
metadata:
  authored_via: "claude-science"
  published_by: "agent"
  published_at: "2026-10-06T23:21:19.915Z"
  authored_by: "unknown"
  last_modified_by: "agent"
  last_modified_at: "2026-10-06T23:21:12.793Z"
---

# Camera trap QC

Failure modes found the hard way on a 26,798-deployment / 60-project continental
dataset. Every one was silent: the analysis ran, produced plausible numbers, and
was wrong. Run these checks BEFORE modelling, not after a reviewer asks.

## Wildlife Insights science-view exports: establish the shape before the content

A "science view" export arrives as two CSVs, an image-level file and a
sequence-level file, and they hold **disjoint project sets** — a WI project is
configured as either an image project or a sequence project. Reference export:
118,583,080 image rows across 3,808 projects, 10,013,698 sequence rows across
1,298 projects, with zero projects and zero deployments in common. Carry a
`source_file` column from the first line of code; never assume a project id or
deployment id is unique across the pair without checking.

**No deployment table ships with the export, and one reconstructs exactly.**
Deployment attributes — coordinates, sensor window, first/last image time — are
denormalised onto every detection row. Group by `deployment_id`, take the
distinct values, and then ASSERT the reconstruction:

```sql
SELECT count(*) FROM (SELECT deployment_id FROM rows GROUP BY deployment_id
  HAVING count(DISTINCT latitude)>1 OR count(DISTINCT sensor_start)>1
      OR count(DISTINCT project_id)>1)
```

This returned 0 of 330,769 deployments on the reference export, which is what
licenses treating the result as the deployment table rather than a guess. A
non-zero count means the export is internally inconsistent and the
reconstruction is unsafe — stop and report it.

**Row grain differs between the two files, and neither is one row per event.**
An image row is one taxon in one photo; a sequence row is one taxon in one
sequence. The "one sequence is not one row" rule below has an image-file
analogue: rows sharing `(deployment_id, timestamp)` are the same photo split by
age/sex class. To put the files on a common footing, collapse image rows with
the 60 s Wildlife Insights sequence interval, chained within a deployment.
Domestic dog in the reference export: 828,560 image rows → 657,410 distinct
timestamped photos → **189,534 independent events**: 4.4x fewer than raw rows, 3.5x fewer than photos. Applying
the same 60 s rule across sequence start times changed the sequence file by only
0.4% (154,517 → 153,838), confirming WI sequences are already built on that
interval and that the collapsed image counts are comparable.

**Datetime columns can hold the literal string `None`.** 2,061,003 image rows
(1.7%) and 37,662 sequence rows. `TRY_CAST` and COUNT the resulting nulls; a
parse failure here is data, not a loading bug, and those rows can never enter an
event count or an effort window.

**`country_code` is absent from `project_metadata` for 38% of deployments**
(80,975 image, 45,225 sequence) — genuinely missing from the JSON, not a parsing
failure. Derive country from coordinates instead.

**No embargo, licence, or fuzzing field exists anywhere in the export**, so
whether a record may be reshared cannot be answered from the files. Ask the
provider for the project embargo setting and the per-deployment upload date; the
embargo clock starts at upload, not at collection, so sensor dates cannot stand
in for it. Whether coordinates were fuzzed IS testable: WI fuzzes sensitive
locations by truncating to 0.1 decimal degree (~11 km), so fuzzed deployments
must sit exactly on a 0.1° grid. Test the grid AND test whether that group is
enriched for IUCN VU/EN/CR species. Reference export: 654 of the 330,759 deployments
carrying coordinates (0.198%; 10 of the 330,769 total have none) sat on the grid and were NOT enriched (17.0% carried a VU/EN/CR species
versus 17.7% of the rest), i.e. coarse coordinate entry rather than fuzzing —
the export held full-precision coordinates for 58,561 sensitive-species
deployments. Check this before resharing anything deployment-level.

**Scale.** The image file is 126.6 GB of CSV. Convert both to column-pruned
Parquet with DuckDB before any QC (`all_varchar=true` on read, then `TRY_CAST`
per column): 49 s and 1.03 GB out for 118.6 M rows, because dropping the
repeated `project_metadata` JSON blob is most of the file. Every check below
then runs in under a second. pandas is not an option at this size.

## Species names: resolve them before anything else

Load **`mdd-taxonomy`** and use it. Multi-project camera-trap exports carry
names from different eras, databases, and identification standards, so the
species column is a merge hazard before it is a data column. That skill's core
rule — resolve every name to a stable Mammal Diversity Database species ID and
compare IDs, never strings, pinned to a specific MDD version — is what makes a
species filter reproducible.

Three camera-trap-specific traps, all of which have bitten:

**Fuzzy name search returns the wrong genus.** Occurrence APIs (iNaturalist
among them) do fuzzy matching on a `name` parameter, so a genus query returns
unrelated taxa. A *Canis* pull came back 31.7% *Vulpes*. Always re-check the
genus of every returned record against what you asked for, or query by taxon ID
rather than name.

**Domestic subspecies contaminate wild-species queries.** *Canis lupus
familiaris* is a subspecies of *Canis lupus*, so an unfiltered wolf query
returns mostly pet dogs. Conventions differ by database — iNaturalist treats
domestic dog as its own species, so an ID-based pull returns none — which is
exactly why you check rather than assume.

**Sentinel species must be identified reliably to be used as clocks.** Section 1
uses a diurnal species as a timezone diagnostic; that only works if the species
is rarely confused. Gray squirrel is safe on this front by day but flying
squirrels are the nocturnal confusion risk, which is why the two-sentinel test
(both species inverted together) is what distinguishes a clock error from a
misidentification rather than either species alone.

**Domestic forms break trinomial reduction — resolve in the right order.**
Accepted name on the full string, then the synonym table on the full string, and
only then reduce a trinomial to its binomial. Wildlife Insights labels dingo
`Canis lupus dingo`; MDD v2.5 lists that exact combination as a synonym of
*Canis familiaris*, so a synonym-first lookup resolves it correctly while a
trinomial-first rule files 109,250 dingo records under *Canis lupus* (Gray
Wolf). WI uses `Canis familiaris`, not `Canis lupus familiaris`, so a *C. lupus*
query does not pull dogs — the hazard here is the dingo name, not the dog name.
Decide explicitly whether dingo belongs in a domestic-dog analysis; MDD says it
is the same species, and WI labels it `wild-animal` while dog is
`domestic-animal`. `Dog-on-leash` is a second WI common name under the same
binomial (13,301 rows): an attribute of the detection, not a taxon.

**The MDD synonym table stores original combinations with the subgenus in
parentheses** — `Macropus (Petrogale) robustus`, `Macropus (Halmaturus) parma`.
Strip parentheticals before matching or every genus change silently fails to
resolve. With that fix, 99.95% of 92.6 M mammal rows in the reference export
resolved to MDD v2.5: 1,406 names matched an accepted name exactly and 139
resolved through synonyms, covering 1.8 M rows whose current name differs from
the string in the file (*Mazama nemorivaga* → *Passalites nemorivagus*,
*Macropus robustus* → *Osphranter robustus*, *Cephalophus* → *Cephalophorus*),
leaving 6 unresolved names and 3 ambiguous splits.

Also watch for captive records when using occurrence data as a range or richness
layer — zoo observations of large carnivores are common in aggregated
occurrence databases and will place a species far outside its wild range.

## 0. Plot before you model — this is a QC step, not a presentation step

Every failure mode below was found by LOOKING at the data. Make these four
plots first, on every new dataset, and read them for defects rather than
for the story. They cost minutes and they change what you do next.

**(a) A map of every deployment.** Reveals cameras outside your intended
study region, coordinate sign errors (points in the wrong hemisphere or in
the ocean), single points standing far from any cluster, and the difference
between a designed grid and an opportunistic scatter. Annotate how many
points you are excluding and why.

**(b) A histogram of gaps between consecutive deployments at the same
location.** The shape tells you the redeployment structure — see section 3.

**(c) Effort over time** (active camera-months per month, all projects
pooled). Shows the seasonal concentration that forces a survey-window
decision, and exposes impossible dates: future end dates, deployments
lasting years, an entire project offset by a year. Plot the FULL date range;
do not clip the axis to where you expect data, or you will hide the outliers
you are looking for.

**(d) A timeline bar per deployment and per subproject** (Gantt style, sorted
by start date). This is the highest-yield plot in the set. Coordinated annual
surveys appear as a clean diagonal staircase of cohorts; any bar spanning
years is a "subproject" that is really several surveys concatenated, and it
will corrupt anything that treats the subproject as one sampling occasion.
In the reference dataset 65 of 1,284 subprojects spanned more than two
years — invisible in any summary table.

Re-plot after each cleaning step. A fix that looks right in a summary
statistic often looks obviously wrong in the timeline.

## One sequence is not one row: age, sex, and group_size
A detection of one species at one camera can occupy several rows, split by age
class and sex. Collapse rows sharing (deployment, taxon, timestamp) into one
photograph and SUM their animal counts before anything else; counting rows counts
annotation granularity.

**Group size means two different things in the two file types, and the column must
say which.** Carry a `group_size_basis` alongside every group size:

- **sequence project**: the sum of the animal counts the observer recorded across
  the sequence. This is a real count of the group and is the column to use for any
  question about group size.
- **image project**: the LARGEST per-photograph count inside the event. The same
  individuals reappear frame after frame, so summing frames multiplies one animal
  into many; taking the maximum avoids that but makes the number a **floor**. Three
  animals that pass one at a time, never sharing a frame, are recorded as a group
  of one.

On the reference export the means were 1.33 (sequence) and 1.79 (image maximum).
That difference is a property of the two counting rules, not of the animals, so
either restrict group-size analysis to sequence projects or stratify by the basis
column. Never pool them silently.

## Richness and species accumulation: species-level records only

Any analysis whose unit is *a species* — richness per camera, species accumulation
or rarefaction curves, community composition, beta diversity — must be built from
records identified **to species**, and nothing coarser. Exclude genus-level records
("Mazama sp."), family- and order-level records, catch-all labels ("animal",
"unknown"), and the platform's own non-detection sentinels (Wildlife Insights
writes "No CV Result" and "CV Failed" *into the species column*, where they will
be counted as species if you filter on non-null alone).

The failure is silent and bidirectional. A genus-level record whose species is
already on the list inflates richness by one phantom taxon; the same record at a
camera where that genus is otherwise unrecorded is a real species you then fail to
count. Neither shows up as an error — the curve just comes out wrong.

Build accumulation curves **separately per class** (mammals, birds, reptiles).
Classes differ by an order of magnitude in both how completely a camera survey
samples them and how far identification has progressed, so a pooled curve is
dominated by whichever class happens to be best-resolved and describes no real
community. Report the per-class species totals the curves were built from, next
to the curves.

State the excluded count when you report richness: "75 wild species from 3,288
species-level detections; 277 genus-level records excluded" is reportable, a bare
richness number is not.

## Pooling traps: two ways to fabricate or destroy a signature

Both of these produced wrong answers in the reference project, and both are silent.

### Never group by name substring across projects

Multi-project exports reuse site names across survey years under different project
IDs. A `str.contains("SiteName")` filter therefore pools cameras from DIFFERENT
projects, and a suffix match like `endswith(("_01","_06"))` then catches twice the
units you meant. In the reference dataset a substring match on one forest name pooled
two independent 12-camera arrays (`Site_25_01..12` from one project and `Site_01..12`
from another), and the pooled hour-of-day statistic sent four never-examined cameras
into the exclusion list.

**Rule: the unit key is always `project_id + deployment_id`.** Filter on the full key
or on `project_id` explicitly, never on a name fragment. Then compute the statistic
PER UNIT and PER PROJECT and look at both before pooling anything. In the reference
case, per-project computation showed the two arrays had opposite patterns -- one
pathological, one indistinguishable from its own siblings.

The mirror error is pooling suspect units with clean ones: a "dead window" in the
suspect cameras vanishes when working siblings fill in those hours. Compute the
signature on the flagged units alone, then show the siblings as a separate contrast.

### Never cluster spatially inside arbitrary pre-blocks

Clustering deployments into arrays is O(n^2) in memory, so it is tempting to
pre-block by a coarse grid and cluster within each block. This SPLITS every cluster
that straddles a block edge: in the reference dataset, 150 km pre-blocks left 863
pairs of cameras under 1 km apart assigned to different arrays.

Patching afterwards by merging any two arrays within the threshold is worse -- it
chains transitively and produced a 746 km "array", exactly the failure the distance
bound exists to prevent.

**Rule: run ONE global clustering.** Complete linkage on 27,000 points is a 2.9 GB
condensed distance matrix and takes seconds; that is affordable, and it guarantees
no array exceeds the threshold. Verify afterwards that every pair of deployments
closer than 1 km shares an array. A small residue is inherent rather than a bug:
two adjacent cameras can belong to arrays whose union would exceed the bound, so
they cannot merge without breaking it (10 of 320,120 pairs in the reference data).
Report the residue; do not chase it.

### Whether to merge overlapping arrays at all is a research-question decision

Nothing above says co-located deployments must always become one array. Pooling is
right when the array is a nuisance grouping -- when you need independent replicates
for cross-validation folds, effective sample size, or a random effect, and two
surveys of the same forest are not independent evidence.

Pooling is WRONG when the repeat is the signal. If you are asking how behaviour
changed between survey years, whether a management intervention shifted activity, or
how a site responded to a new road or altered access, then year-within-site is the
contrast of interest and averaging it away destroys the study. The same applies to
a site resampled under different protocols or camera placements.

Decide before clustering, state the decision in the methods, and if both framings
are in play, build both array definitions and carry the choice as an explicit
argument rather than a buried default.

## The five checks, in order

### 1. Timezone storage is per-deployment, not per-project
Do NOT trust the timestamp column, its suffix, or a project's documentation. A
`Z`/UTC suffix frequently holds local wall-clock time; some projects in the same
export hold real UTC; and individual cameras inside a correct project can be
misconfigured by an arbitrary offset.

**Diagnostic: use species with known, extreme diel behaviour as clocks.**
Gray squirrel, fox squirrel, chipmunk and wild turkey are strictly diurnal —
under correct local time under ~10% of their detections fall at night. Raccoon,
opossum and skunk are the mirror test at ~90% nocturnal. Two species pointing
opposite directions is what makes the test diagnostic.

**Compute sunrise/sunset in LOCAL CLOCK hours, or every test below is biased.**
This is the single most consequential detail in this skill. Camera timestamps are
clock time; a solar-time sunrise is offset from clock time by the site's longitude
within its time zone (up to an hour, largest at zone edges) plus daylight saving
(another hour). An earlier version of `solar_window()` here ignored both, and the
resulting ~1 h bias made ordinary crepuscular activity at western-edge sites read as
nocturnal — generating false "broken camera" flags that were only caught when a
site's real sunset was checked by hand.

Get the zone from the IANA database (`timezonefinder` + `zoneinfo`), never from
`round(lon/15)`: US zone borders follow state lines, not meridians, and Arizona does
not observe DST. Hand-coded boundaries failed on Nashville, El Paso and Phoenix.
The corrected `solar_window(timestamps, latitude, longitude)` validates to within
14 min of published sunrise/sunset across 9 sites in 4 zones.

**A sentinel set that works outside North America.** The four sentinels above
are North American; a global export needs groups that occur everywhere. Use
**diurnal = genus *Sciurus* plus class Aves excluding Strigiformes (owls) and
Caprimulgiformes (nightjars)**, mirrored by **nocturnal = Strigiformes plus
*Didelphis*, *Procyon lotor*, *Genetta* and *Rattus***. On the reference export
these landed at 8.4% and 92.4% of detections at night respectively (project
medians 4.2% and 96.8%) — compute that pair of numbers first, because it
validates the sentinel set on YOUR data before any project is flagged by it.
Humans (`taxonomy_subtype='human'`) are a usable third diurnal sentinel, median
2.5–4.3% night, worth adding where neither group reaches the minimum count.

**The nocturnal mirror is what separates a broken clock from an unusual site.**
A clock error inverts both groups at once; a genuinely odd site moves one. On
the reference export 75 projects crossed the 20% diurnal-night threshold with
the UTC signature, and 6 showed both groups inverted together (diurnal >50%
night AND nocturnal <50% night) — a combination no animal community produces.

**Coverage is limited by project SIZE, not by sentinel choice.** A diurnal
sentinel reached 2,752 of 5,106 projects at a 60-detection minimum; any
sentinel including humans reached 3,177 (62.2%). The 1,929 projects with no
sentinel hold 1.2% of all rows, median 37 rows each — 1,505 of them have under
200 rows in total. Adding more sentinel taxa does not fix that. Report those
projects as **unscreened**, never as passing.

**Screen at the DEPLOYMENT level, not the project level.** Clock errors enter per
camera and per upload. A project with one misconfigured camera is not a broken
project: flagging the whole project discards hundreds of good deployments, and a
single-camera fault inside a clean project goes unnoticed because the project
median absorbs it. On a 330,769-deployment export, moving the same screen from
project to deployment changed the result from "75 suspect projects" to **2,888
suspect deployments out of 123,789 testable (2.3%)**, which is a usable exclusion
list instead of a blunt one.

Deployment-level sampling that worked on that export: **minimum 20 sentinel
detections, capped at 200 per deployment per group**. The minimum is what limits
coverage — 205,359 deployments never reach 20 and are reported `unscreened` — and
the cap stops one 40,000-detection camera from dominating its own test.

**Cameras genuinely on UTC cannot be tested, and must not be scored as passing.**
The UTC test shifts each timestamp by the site's own offset from UTC and asks
whether the day-night pattern improves. For a camera in Britain, Portugal, Iceland
or West Africa that offset is near zero, so the shift changes nothing and the test
has no power. Give those deployments their own status (`untestable_for_utc`,
|offset| < 1 h; 1,621 of 330,769 on the reference export) instead of letting a
no-change result read as a pass. A pass there is an artefact of geography.

**Project level: a real hypothesis, and safe to act on.**
```
diurnal-sentinel night fraction > 0.20  AND  adding the site's true UTC offset
lowers it   ->  the project stores UTC
```
The shift is FIXED by the time zone, not fitted, and every camera in the project
agrees. Two cautions learned the hard way:

- **Verify against the source metadata before acting.** A single-sentinel,
  single-threshold screen over-flagged badly in the reference project: 15 projects
  were called UTC, but the published archive documentation stated local standard
  time, and multi-species retesting split the group. Where an original data archive
  exists, prefer replacing suspect data with it over correcting in place.
- **The offset is DST-aware.** Matching individual records against a published
  archive showed the corruption was a local→UTC conversion that honoured daylight
  saving, so a flat longitude shift would have been an hour wrong for most records.

**Non-adjusting camera clocks are a separate, mostly undetectable problem.** Some
cameras auto-adjust for DST and some do not, so a fraction sit exactly 1 h off. Two
findings: (a) within a season-restricted window containing no transition, a 1 h
offset is only ~0.55 SD of natural between-camera variation in activity timing, so
individual cameras are NOT identifiable and correction is unjustifiable; (b) if your
data spans a DST transition, each camera becomes its own control — subtract 1 h from
post-transition records and see whether it restores that camera's own pre-transition
level. In the reference data this identified 29% of testable cameras as
non-adjusting and confirmed 24% as adjusting. Rule out day length first: measure the
nocturnality-versus-daylength slope in a transition-free stretch (about 1 pp per hour
of day length lost) and check it against the observed jump.

**Camera level: DETECT, then verify with evidence outside the diel data.
Never shift a camera to make it match the species mean.** That reasoning cannot
distinguish a broken clock from a genuinely unusual site, and applying it erases
exactly the local behavioural variation you are usually trying to measure.

Detection (screening only): segment the deployment (see below) and test whether
strictly diurnal species are logged at night — over ~50% within a segment is a
candidate.

*Do not* fit an offset per camera and treat the improvement as evidence. With 25
candidate shifts and few species, some shift always fits better: on 1,142 cameras in
arrays that PASSED the array-level check, a non-zero offset "improved" fit by >50%
for **44.5%** of them. That is the false-positive rate of the method. The same
statistic on suspect arrays was 60.7% — barely 1.4x enrichment, which is why an
offset search cannot identify individual cameras and why any such result needs a null
run on known-good units before it means anything. `best_offset()` in this skill is
documented as diagnostic-only for exactly this reason.

Confirming evidence, in order of strength:
1. **A human looks at the images.** A strictly diurnal species timestamped at
   night: is the frame dark or daylight? This is definitive.
2. **A structurally impossible gap.** Four cameras in one reference dataset had a
   9-hour window (04:00-12:00) with zero diurnal-species detections while their
   working siblings at the same site showed the correct inverse. No animal
   community produces that; it is safe to act on.
3. **The reset signature.** Malfunctioning cameras often start at midnight on
   1 January. Its ABSENCE is weak evidence of health (it was absent from 26,763
   of 26,778 deployments in the reference data, and from all 29 candidates), but
   its presence is strong evidence of a fault.
4. **Timestamps outside the recorded deployment window.**
5. Species-ordering inversion — a diurnal sentinel more nocturnal than a
   nocturnal one — is a useful screen (2.7% of clean cameras vs 11.5% of suspect
   ones) but is NOT sufficient to act on, and it also MISSES real faults: in the
   reference data a camera the PI confirmed broken from its images scored +0.20 on
   the ordering test, i.e. would have been cleared. Its actual evidence was the
   impossible detection gap (item 2). Run several independent tests; no single
   statistic both detects and clears.

**Segment before testing: partial shifts are the common case.** A clock breaks
or is corrected mid-deployment, so a whole-deployment verdict is wrong for most
affected cameras — 14 of 29 in one dataset, 13 of 21 in another. Bin detections
by day, mark days where diurnal species exceed 50% nocturnal, and group
consecutive runs.

**Set `min_per_day` to at least 3.** With `min_per_day=1` a single night-stamped
detection makes that whole day "100% nocturnal", so the screen flags a large share
of perfectly good cameras: on one reference project it returned 545 bad segments at
`min_per_day=1` versus zero on the same known-clean cameras at `min_per_day=3`.
The screen exists to shortlist candidates for the confirming evidence above, never
to produce a verdict — treat its output as a queue, not a decision.

**Verification images MUST come from inside an affected segment.** In the
reference case a PI checked an image and correctly reported it looked fine — it
came from the one clean week of an 8-week-shifted deployment, because the image
had been chosen for distance from twilight with no regard for when in the
deployment it fell. That nearly cleared a genuinely broken camera.

**Clock errors are per-camera, not per-site.** Affected and clean cameras sit
side by side: 4 of 11 at one site, 4 of 8 at another, 2 of 24 at a third, with
different best-fitting offsets per camera within one site. No site- or
subproject-level fix applies, and averaging a site hides them.

**When a camera is confirmed bad, prefer dropping it to shifting it** unless the
mechanism is understood and fixable at source. In the reference dataset dropping
22 confirmed deployments cost 0.32% of detections and 0.16% of effort, emptied
no array, and left no camera above 50% — a trivial price for not fabricating
timestamps.

### 2. Array definitions: check extent, never trust a fallback
Cameras cluster in arrays; the array is usually the analysis unit. Pipelines
that infer arrays from a metadata column fall back to "whole project = one
array" when the column is missing, silently.

**Check: max pairwise distance within every array.** Properly defined arrays
have median extent of a few km. In the reference dataset 34 arrays were
whole-project fallbacks holding 37% of deployments, one spanning 4,061 km.

Rebuild in two stages: (a) split by whatever subproject/county/site column
exists — it is often populated for 99%+ of the fallback rows and simply was not
used; (b) apply **complete-linkage** hierarchical clustering at your scale
threshold to anything still too dispersed. Complete linkage GUARANTEES the
bound; single linkage chains through intermediate cameras and left a 196 km
array under a 25 km threshold.

### 2b. Repair the operating window; do not discard the deployment
Stated windows disagree with the photographs constantly: a window that is missing,
backwards, zero-length, in the future, or that fails to contain the images. The
instinct is to drop those deployments. On the reference export that cost 35,681
deployments, 11% of the dataset, almost all of them ordinary cameras with a
mistyped end date.

Rebuild the window instead: where the stated window disagrees with the
photographs, take first photograph to last photograph and set a `window_repaired`
flag. 35,811 deployments were repaired this way and the exclusion count fell from
35,681 to **6,602 (2.0%)**, which are only the deployments with no usable
photographs at all. "No first-image time" means the camera produced nothing; that
one is genuinely unusable for anything timed and is the only date defect that
cannot be repaired.

**Bound photograph timestamps before you take the first and last.** The repair
trusts the photographs, so one corrupt photograph destroys the deployment. Drop
timestamps outside a plausible range (1990 to now) BEFORE aggregating. On the
reference export 429 deployments carried photographs stamped as far out as the
year 9095, and a single one of them gave a four-month deployment **3.85 million
camera-days** of effort. Record the count per deployment
(`n_impossible_image_dates`) so the defect is visible rather than silently
repaired.

### 2c. Row ordering inside a window function must be deterministic
A gap analysis that orders deployments by start time within a station will meet
ties, because several cameras at one station are often entered with the same start
instant. `row_number() OVER (PARTITION BY station ORDER BY start)` then assigns
consecutive pairs arbitrarily and the gap counts move between runs of the same
script on the same data. Add the primary key as a tiebreaker
(`ORDER BY start, deployment_id`). This was caught only because a figure
regenerated from the saved pipeline disagreed with the text written from an
earlier run by 40 pairs.

### 3. Repeated deployments at one station — three cases, three fixes
The same coordinates recur in the deployment table for several different reasons,
and conflating them corrupts either effort or sample size. Plot the
gap-between-consecutive-deployments histogram (section 0b); it is usually
sharply bimodal, which makes the cases separable empirically rather than by
assumption.

**First, build the station, because exact coordinate matching is wrong.**
Coordinates recorded by hand or from different GPS fixes drift by a few metres, so
matching on the exact pair splits one physical station into several. Cluster
deployments whose coordinates fall within ~10 m (KD-tree plus connected components)
and give each cluster a **derived placename**. On the reference export 158,092
recorded placenames collapsed to 141,428 derived ones, a mean of 2.34 deployments
per station. Do this before any gap analysis, or the gaps are computed between
records that were never at the same place.

**Case A — back-to-back, gap of days or less: ONE STATION, but NOT one
deployment.** A camera serviced, an SD card swapped or a record split at an
arbitrary boundary produces two rows for what is one survey. Treat them as one
station for sampling: they are not independent sites, and counting them as two
inflates the deployment count and creates noisy low-count units.

**Do NOT merge them into a single deployment spanning both dates.** An earlier
version of this skill recommended exactly that, and it is wrong whenever the two
records do not abut: the merged window includes the days the camera was not
recording, and that time enters effort as if it had been surveyed. Measured on the
reference export, spanning the gaps of the 66,941 consecutive pairs that have one
would have added **18.7 million camera-days, 106% of the real effort in the
export** — the fabricated effort would have exceeded the measured effort. Effort
never runs across a gap. Each record contributes only its own recording period,
and the two share a station identifier.

**Case B — annual re-survey, gap of ~a year: keep as separate deployments, but
pool into ONE array.** Coordinated surveys re-deploy at the same station each
year. These are genuinely different survey occasions, so do not merge the
records — but if array identity includes project or year, one physical site
becomes N arrays and inflates every array-level sample size. Reference: 2,357
repeated locations, 1,880 split across multiple arrays, turning single sites
into 4,594 arrays; pooling by location collapsed 679 arrays to 347.

Case B is especially damaging to fine-scale variance claims: two arrays at the
same site have identical covariates and zero separation, so "variation below
25 km" silently absorbs the same site measured in different years.

**Case C — two cameras at one station, running at the same time: drop one from
effort.** Paired cameras set to photograph both flanks of an animal are put out
together and collected together, so their windows start AND end within a few days
of each other. Matching both ends is what separates a true pair from two cameras
that happened to overlap at one station across seasons. Counting both doubles the
effort at that station while the detections stay the same, which halves the
apparent detection rate there.

Detection rule that worked: deployments at one derived placename whose starts and
ends both fall within 7 days, with a cap on effort (730 days) so that a
mis-specified long window cannot swallow a whole station. Mark the lower-yield
camera `paired_camera_redundant` and exclude it from effort, keeping its
detections available for occupancy or species lists. Reference: 9,346 true pairs,
618,359 camera-days removed, 3.5% of the total.

Three or more cameras concurrent at one coordinate is NOT a pair. That is an array,
or a project that recorded coordinates at site level rather than camera level.
Reference: 6,713 such stations covering 74,901 deployments. Flag them
(`flag_shared_coordinate`) and leave the treatment to the question, because
dropping all but one would discard a real array design.

### 3b. A deployment longer than the survey: clip, split, or keep

A stated window of years is usually a metadata defect rather than a long survey,
and the three cases need opposite fixes. Plot detections per day against the
stated window for every deployment over two years; the picture decides it.

Reference export: 3,073 deployments had windows longer than two years, but about
2,000 of those had `sensor_end` beyond the export date (as far out as the year
9094) and no splitting can repair them. Of the 1,089 with plausible windows:

- **752 (69%) — clip the window.** Median stated window 1,096 days against a
  median detection span of 39 days. The end date is wrong; the deployment is
  short. Clip to the detection span, do not split.
- **282 — split.** Detections cover most of the window but contain real
  silences. These became 1,639 segments, 2 to 12 per deployment.
- **45 — keep.** Genuinely continuous across a long window.
- **10 — no usable detections.**

**Split rule: a silence of at least 30 days AND at least 10x that camera's own
median inter-detection interval.** The second clause is load-bearing. Median
inter-detection interval on these deployments was 1.5-2 days, so a flat 30-day
rule is right for an active camera but shreds a sparse one that legitimately
fires every 10 days. Both thresholds belong in the output table so the split can
be re-cut without re-deriving it.

Separate the cases with two ratios per deployment: **window coverage**
(detection span / stated window; below 0.5 means clip) and the segment count
from the split rule (above 1 means split).

**Apply the triage to EFFORT, not just to a report column.** A clipped deployment
contributes its detection span, a split one the sum of its segments, and one with
no usable detections contributes nothing. A verdict written to a CSV and not
applied to the denominator changes nothing.

**Lower the threshold and report the sensitivity.** Two years is too generous: a
camera with a three-month window and a two-month silence has the same problem. On
the reference export, screening every deployment over **90 days** put 60,295 under
inspection, of which 35,786 were kept, 12,207 split, 11,868 clipped and 434 had no
usable detections.

The split rule has two tunable numbers (minimum gap, and multiple of that camera's
own median gap between detection days) and they matter. Across six threshold pairs
on the same 59,861 deployments, the number split ranged from 6,791 (90 days, 10x)
to 23,780 (15 days, 5x), a factor of 3.5. Publish that table next to whichever
setting you chose; the rule is defensible, the specific numbers are a choice.

### 4. Sun-anchored time breaks the effort offset
Sun-time transformation (Vazquez et al. 2019 MEE) rescales each day so sunrise
and sunset land on fixed anchors. Per-bin effort is uniform in CLOCK time —
cameras run continuously — but NOT in sun time: when day length differs from the
reference day, day bins and night bins get different real-time durations.

Reference: all 22,912 deployments had varying per-bin effort in sun time, up to
2.1x within one deployment; zero varied in clock time. The bias runs in ONE
direction and, because day length covaries with latitude and season, appears as
a believable latitudinal gradient rather than noise.

**Always carry an exact analytic per-bin effort column** and use it as the
offset (`offset(log_effort)` in a count model). Do not assume constant effort.
This consequence is not spelled out in the source literature.

### 5. Detection rate and diel metrics share a denominator
Regressing a diel metric on the focal species' own detection rate is partly
arithmetic: both derive from the same event counts, and low-count arrays have
noisier metrics (a precision confound that manufactures relationships on its
own).

**Run a simulated null.** Per array, simulate counts from a FIXED
species-mean curve shape scaled to that array's observed event total and its
per-bin effort, with dispersion matched; recompute metrics through the identical
pipeline; re-run the regression. Report `artifact_ratio = null effect / observed
effect`.

Reference ratios: crepuscular 0.03 and % nocturnal 0.11 (clean); concentration
0.60 (contaminated); peak timing 0.97 and activity breadth 1.92 (the null
EXCEEDS the observed effect — uninterpretable).

**The artifact is specific to the species' OWN rate.** Regressing on a
DIFFERENT species' detection rate (predator, competitor) does not share the
denominator — median ratios there were 0.10-0.12, and simulating the predator's
counts as well REDUCED the null. So a predator-rate covariate is safe where a
self-rate covariate is not.

## Two analysis conventions that follow

**Restrict to one season, then control timing WITHIN it.** Multi-project
continental data is usually autumn-concentrated (Snapshot USA runs then), so a
seasonal window prevents space/season confounding. But arrays differ in when
inside the window they ran, and that predicts diel metrics (3-7 percentage
points of nocturnality per 30 days in the reference data). Include an
effort-weighted mean day-of-year term. Do not extrapolate its slope across a
window most arrays never spanned, and note that sun-anchored time already
removes the day-length geometry, so the term captures phenology, not daylight.

**A random intercept per array is not enough.** It absorbs detection LEVEL, not
curve SHAPE. Use random harmonic coefficients per array if you need array-level
diel structure.

## Presence/absence covariates and regional confounding
A predator-presence covariate can be a near-synonym for a region. Check the
geographic split before interpreting: puma presence appeared at 20 of 532 deer
arrays, 16 of them western, so a continental contrast was 41% an east-west
comparison. Restrict to the region where the predator plausibly occurs, and
report the minimum detectable effect — a within-region non-result on 30 arrays
is not evidence of absence.

## Domestic animals: was there a person with it?
A domestic dog or cat in front of a camera is a different ecological object
depending on its company, and the camera is the only witness. Three levels work
better than a binary:

1. **with a person** — a person in the SAME detection event (same sequence id in a
   sequence project; a person photograph inside the event or within the
   independence interval of its ends in an image project)
2. **near a person** — no person in the event, but a person at that camera within a
   chosen window (30 min worked on the reference export)
3. **free-ranging** — no person at that camera within the window

**Count vehicles and bikes as people.** Every vehicle, ATV, truck, snowmobile,
motorcycle, boat and e-bike label carries a driver or rider. Omitting them
undercounts accompaniment materially. Leave out object labels that imply nobody
(Trash, Measurement Scale). Watch for horseback-rider labels, which some platforms
file outside the obvious human category.

**Validate the level-2 window against a day-shifted null, not against intuition.**
Move each animal detection one day forward, and separately one day back, and rerun
the rule against the REAL person detections. A day shift preserves hour-of-day and
season, which are what drive when people and animals pass a camera, and destroys
only the pairing between a particular animal and a particular person. Whatever the
rule still finds is coincidence. On the reference export the excess over the null
peaked near 60 min, but the share of flagged detections the null already explained
rose from 67% at 30 min to 72% at 60 min and 82% at 240 min: pick the turn, and
publish the table so the reader can see what the choice cost.

**Measure recall with a label you already trust.** A "dog on leash" label is an
independent witness that a person was present, so the share of leashed detections
the rule recovers IS its recall: 85% in the event, 89% within 30 min. The misses
were not a blind rule (only 77 of 695 were at cameras that never label humans) but
annotation practice, where a leash is visible and the handler is out of frame.
Report the free-ranging rate as an upper bound accordingly.

**Remove the field crew's own animals.** A dog photographed with a person within
30 min of a deployment's first or last photograph is the camera trapper's dog at
setup or pickup. That was 4,972 of 360,118 dog detections (1.4%), and 41 of
146,793 cat detections — the asymmetry is itself a check that the filter is doing
what it claims.

**The three levels are worth the trouble because they separate.** Modelled as
negative binomial counts with log effort offset and country as a fixed effect, on
the reference export: a road or hiking trail multiplied the accompanied dog rate
by 2.56 and the free-ranging dog rate by 1.90, but the free-ranging CAT rate by
1.00 (0.93–1.08). Bait cut accompanied dogs to 0.19x while leaving free-ranging
dogs at 1.11x and cutting free-ranging cats to 0.45x. Pooling the levels, or
pooling the two species, would have hidden all of it.

**Fit a negative binomial, and check the dispersion.** Detections cluster hard:
alpha came out 23–62 across these models, so a Poisson fit would have produced
confidence intervals several times too narrow. Estimate alpha with the
Cameron-Trivedi auxiliary regression of the squared Poisson residual on the
Poisson mean, then hold it fixed. Drop countries with fewer than ~5 detections at
a level: their dummies are perfectly separated and have no finite coefficient.

**Camera height is a nuisance covariate you cannot omit for small animals.**
Chest-height cameras recorded 0.71x the free-ranging cat rate of knee-height ones
and 1.02x the dog rate. A cross-country cat comparison that ignores height
compares survey designs.

## Reporting
State per-project timezone verdicts, array-definition rules with the resulting
extent distribution, how repeated sites were pooled, and null-test artifact
ratios for any rate-based predictor. Reviewers cannot see these choices from a
methods sentence, and every one changes the numbers.
