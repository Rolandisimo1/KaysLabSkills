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

A camera-trap "sequence" is one detection event, but the observations table
carries **one row per (species x age x sex) class within that event**. A doe with
two fawns is legitimately two rows on the same sequence_id: one Adult/Female with
group_size 1, one Juvenile/Unknown with group_size 2. Multiple species in one
event also produce multiple rows.

So `sequence_id` is NOT a unique key, and the correct handling depends on your
response variable:

| Response | Rule |
|---|---|
| **Detection events** (activity patterns, diel timing, occupancy) | Deduplicate on `(deployment_id, sequence_id, species)`. Extra age/sex rows are the same event and would otherwise be double-counted. |
| **Abundance / animals counted** (detection rate weighted by group size) | **SUM `group_size` across the age/sex rows** within each `(deployment_id, sequence_id, species)`. Deduplicating instead silently discards animals. |

**Check: count how many `(sequence_id, species)` groups vary in `age` or `sex`.**
Reference (Mast and Mammals, 22,923 events): 635 sequence_ids had multiple rows —
127 genuinely multi-species, 508 the same species split by class. Within those,
474 groups varied by age and 493 by sex. Deduplicating for events was correct and
changed no event count, but it understated total animals by 648 of 29,424
(**2.2%**) — invisible unless you check, and it biases group-size-weighted
abundance downward wherever family groups occur.

Never assume the duplication is an export error. It is the data model, and the
age/sex breakdown is real information you may want.

**Do not report this as a data-quality defect.** Multi-row sequence_ids are expected
structure, not a mistake by the data provider, and listing them in a QC report or
dashboard as an "issue" misleads the project team into thinking something is wrong
with their data. Two legitimate causes: (a) the same species split into age/sex
classes, and (b) two or more species in one event. Both are correct. State the
deduplication rule as an *analysis convention* for whoever uses the data next, and
keep it out of the defect list.

The same applies to other provider-side properties of the platform's data model.
Wildlife Insights leaving `common_name` empty for some taxa, or not populating
`cv_confidence` in an export, or an `is_blank` flag that disagrees with a "Blank"
label, are platform behaviours, not errors the project team introduced or can fix.
Note them as handling conventions where they affect your code, but do not put them
in a defect list. Reserve that list for things the project can actually act on:
wrong coordinates, duplicated deployments, broken clocks, mis-entered dates.

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

### 1. Timezone storage is per-project, and per-camera
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

### 3. Repeated deployments at one location — two cases, opposite fixes
The same coordinates recur in the deployment table for two completely different
reasons, and conflating them corrupts either effort or sample size. Plot the
gap-between-consecutive-deployments histogram (section 0b); it is usually
sharply bimodal, which makes the two cases separable empirically rather than by
assumption.

**Case A — back-to-back, gap of days or less: MERGE into one deployment.**
A camera serviced, an SD card swapped, a battery changed, or a record split at
an arbitrary boundary produces two or more rows for what is one continuous
survey. Treating them as independent deployments double-counts the site within
a single survey occasion, inflates the deployment count, and — if you compute
per-deployment detection rates — creates spurious low-count units whose noisy
metrics feed straight into the precision confound of section 5. Merge rows at
identical coordinates whose gap is at or below a few days into a single
deployment spanning the union of their dates, summing effort. Watch for
NEGATIVE gaps: overlapping deployments at one location mean two cameras at one
station or a data-entry error, and they need resolving, not merging.
Reference: 1,813 of 6,368 consecutive same-location pairs were 7 days or less
apart, 191 of them overlapping.

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

**Caveat on pooling.** If a site genuinely changed between years — new road,
altered hunting access, a burn — pooling averages away real variation. Before
pooling, check whether the same site's estimates differ more across years than
across cameras within a year; if they do, year is a real effect at that site and
should be modelled rather than absorbed.

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

## Reporting
State per-project timezone verdicts, array-definition rules with the resulting
extent distribution, how repeated sites were pooled, and null-test artifact
ratios for any rate-based predictor. Reviewers cannot see these choices from a
methods sentence, and every one changes the numbers.
