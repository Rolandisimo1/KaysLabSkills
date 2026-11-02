---
name: step-selection-functions
description: >-
  Build, run, interpret, and audit integrated step-selection functions
  (SSF / iSSF / iSSA) for animal movement and habitat-selection analysis in R.
  Use whenever a task involves step-selection analysis, habitat or resource
  selection from GPS/telemetry tracks, conditional logistic regression on
  used-vs-available steps, movement kernels (step-length and turn-angle
  distributions), relative selection strength (RSS), annotating steps with
  environmental covariates, or the R packages amt, survival (clogit), glmmTMB,
  or mgcv. Also use to review, debug, or audit existing step-selection code
  against the method rather than against itself. Triggers include fitting or
  running an iSSF, auditing SSF code, generating random steps, annotating
  covariates onto steps, updating movement parameters, interpreting selection
  coefficients, and checking goodness of fit — even when the phrase step
  selection is not used. Prefer it over improvising from memory; it encodes many
  easy-to-miss correctness pitfalls.
---

# Step-Selection Functions (SSF / iSSF)

## What this skill is for

Two jobs, often in the same session:

1. **Generate/run** a correct SSF or iSSF pipeline: clean → project → resample →
   steps → random steps → **annotate covariates** → **diagnose selection** → fit →
   update movement kernel → interpret → validate → optionally simulate. The
   annotate → diagnose → fit sequence is the core, not just the final `clogit`.
2. **Audit** existing SSF code against the *method*, not against itself. When
   reviewing code, work from the first-principles checklist below, name the
   specific correctness issue and the correct pattern, and do not normalize
   whatever the code happens to do.

Default to writing R the user runs, unless asked to execute it. Match their
packages and conventions when known, but never adopt a convention that is
methodologically wrong just because existing code uses it.

## Dataset-agnostic operation (do not assume a schema)

This skill must work on any movement dataset. **Never assume column names**
(e.g. do not hard-code `step_id`, `case_`, `point_id`, `x_`/`y_`) or a fixed CSV
layout. Instead, at runtime:

- **Inspect first.** Read the columns actually present. Infer roles by content and
  common conventions: a binary used/available flag (values like TRUE/FALSE, 1/0,
  "used"/"avail"), a stratum/step id (one value per matched used+random set), x/y
  coordinates (and whether they are projected metres or lon/lat degrees), a
  timestamp, and an animal/individual id.
- **Confirm or ask.** If role assignment is ambiguous, state the inferred mapping
  and ask the user to confirm the few uncertain columns — do not guess silently.
- Treat any covariate-comparison workflow (e.g. comparing two remote-sensing
  greenness products) as a *pattern to configure*, not a fixed path. See
  `references/covariate_annotation.md`.

## The one idea to keep straight (model vs. inference)

The SSF *model* is a redistribution kernel: the next location's probability is
proportional to a **movement kernel** φ (step-length + turn-angle distributions,
"how it moves absent selection") times a **habitat-selection function**
w = exp(β·covariates) ("where it prefers absent movement limits"). See Avgar et
al. 2016; Fieberg et al. 2021; Michelot et al. 2024.

Conditional logistic regression, the "used vs. available step" framing, and the
random ("control") steps are an **inference device** — a numerical approximation
of an integral — *not* the model and *not* a biological availability set (Michelot
et al. 2024). Consequences:

- Random steps are integration points. More is better for the approximation; their
  distribution affects precision, not the target parameters.
- CLR equivalence holds only when φ and w are both log-linear. It is not a case–
  control study and does not license every modeling choice.

## Correct pipeline (canonical order)

Do these in order; skipping or reordering the first three causes the most common
serious errors.

1. **Clean, then PROJECT to an equal-distance metric grid (never lon/lat).** Step
   lengths and turn angles are computed in the track's CRS units; in degrees they
   are distance-distorted and angle-warped, and the distortion grows with
   latitude. Pick **one appropriate metric grid per study area** — a local UTM
   zone, or an equal-area projection at high latitude (e.g. Alaska Albers,
   EPSG:3338). Work in **consistent units (km recommended)**. Comparability across
   analyses comes from **consistent units, not a shared projection**: habitat
   coefficients are projection-invariant, and step-length parameters compare once
   units match. Note: the gamma *scale* and any *distance-valued covariate* (water
   distance, distance-to-road) carry length units and must share units; gamma
   shape and von Mises concentration are dimensionless. Use
   `amt::transform_coords()` *before* `steps()`; then `sl_` is metric — no custom
   haversine.
2. **Enforce a regular fix rate → bursts.** iSSA assumes constant step duration.
   Use `track_resample(rate, tolerance)` and build steps within bursts
   (`steps_by_burst()`). Do not pool steps of mixed `dt_`. If missing fixes force
   irregularity, see `references/incomplete_data.md` (forgiveness / dynamic+model)
   rather than silently discarding data.
3. **Tentative movement distributions** from observed steps: gamma (or exponential
   / log-normal) for step length, von Mises for turn angle (`fit_distr()`).
4. **Generate random steps** (`random_steps()`): use enough control steps
   (commonly 25–200; the low default is often insufficient). One matched stratum =
   1 observed step + its N random steps, with a unique stratum id.
5. **Annotate covariates onto every point — the core, not a side step.** Extract
   or join each layer at the step **end** (selection) and, for habitat-dependent
   movement, the **start** (movement interactions; `extract_covariates(where =
   "both")`). Reproject each raster to the working grid at extraction so every
   layer is sampled on the same metric grid. See
   `references/covariate_annotation.md` (and `references/covariate_palette.md` for
   a sourced starting menu of covariates by system).
6. **Diagnose selection before modeling.** Used-vs-available histograms per
   covariate and selection-ratio w(x) plots to see the signal; re-check after
   fitting. First-class output. See `references/selection_diagnostics.md`.
7. **Include movement covariates matched to the assumed distribution.** For gamma
   + von Mises: `sl_` + `log(sl_)` + `cos(ta_)`. Their coefficients *are* the
   estimators that correct the tentative kernel (Avgar 2016). Include the
   **endpoint** habitat term; omitting it collapses the model.
8. **Fit** the right estimator for the design:
   - Single individual → `fit_issf()` / `survival::clogit()` with `strata()`; the
     model-selection loop (LRT/AIC/VIF/forest plots) lives in
     `references/fit_clogit_and_model_selection.md`.
   - Multiple individuals, population inference → **do not pool into one clogit.**
     Use the Muff 2020 / Chatterjee 2024 mixed model (`glmmTMB` Poisson trick,
     random slopes) or a two-step approach. See
     `references/mixed_issf_glmmtmb.md`.
   - Non-linear / spatial / varying-coefficient / random smooths → `mgcv`. See
     `references/smooth_issf_mgcv.md`.
9. **Update the movement kernel** (recover habitat-independent parameters) —
   routinely skipped. Formulas below; all distributions in
   `references/movement_kernel_corrections.md`.
10. **Interpret** via relative selection strength (`log_rss()`), not raw
    coefficients alone; watch the categorical reference-level trap.
    `references/interpretation_rss.md`.
11. **Validate**: used-habitat calibration plots and simulation-based lineups —
    check the ±π turn-angle peak and step-length/turn-angle cross-correlation the
    default kernel misses. `references/goodness_of_fit.md`.
12. **Predict / space use** if needed: redistribution kernel + path simulation →
    transient or steady-state UD. `references/simulation_ud.md`.

## Movement-kernel correction formulas (gamma + von Mises)

Tentative gamma shape `k0`, scale `θ0`, von Mises concentration `κ0`, with fitted
coefficients on the movement covariates:

- Updated shape:  `k̂ = k0 + β_log(sl)`
- Updated scale:  `θ̂ = 1 / (1/θ0 − β_sl)`
- Updated conc.:  `κ̂ = κ0 + β_cos(ta)`   (von Mises mean 0 if `β_cos(ta) ≥ 0`, else π)

For exponential / log-normal step lengths and habitat-dependent kernels, use
`references/movement_kernel_corrections.md` or amt's `update_sl_distr()` /
`update_ta_distr()`. Verify the update rather than trusting a helper blindly — the
required covariates depend on the assumed distribution (Fieberg 2021, Appendix C).

## Correctness audit checklist (first-principles red flags)

When reviewing code, check each and report the specific violation + fix:

1. **Geographic CRS.** Track built in lon/lat and steps/`random_steps` run in
   degrees → distorted availability and warped angles. Fix: project to a metric
   grid first.
2. **Unit inconsistency.** Distance-valued quantities (step-length scale, distance
   covariates) not on a common unit across analyses. Fix: standardize units (km).
3. **Mixed step durations.** No `track_resample()`; varying `dt_` pooled into one
   tentative distribution. Fix: resample to bursts; handle irregularity per
   Hofmann 2024.
4. **CRS mismatch at extraction.** Covariate raster in a different CRS than the
   points when sampled. Fix: reproject each layer to the working grid at extract.
5. **"Population" = one pooled clogit.** Pseudoreplicates, ignores among-animal
   variation. Fix: `glmmTMB` mixed iSSF or two-step.
6. **Movement kernel never updated.** `sl_`/`log(sl_)`/`cos(ta_)` included but
   coefficients never back-transformed. Fix: apply corrections; report the kernel.
7. **Missing endpoint effect** or wrong movement covariates for the chosen
   distribution. Fix: include end-of-step habitat; match covariates to φ.
8. **Too few control steps** with no stability check. Fix: increase N; confirm
   estimates stabilize.
9. **Strata / stratum-id errors** (non-unique ids, used step not in its own
   stratum, id collisions across individuals). Fix: unique stratum id per set.
10. **No selection diagnostics / no GOF / no RSS.** Coefficients reported raw with
    no signal check or validation. Fix: w(x) plots; UHC + lineups; `log_rss`.
11. **Estimability not checked** for movement parameters (can be extremely
    imprecise even at large N; Avgar 2016). Fix: report SEs, check sensitivity.
12. **Data-driven selection overfit.** Stepwise/AIC dredging over many covariates
    with no hypothesis structure. Fix: hypothesis/DAG-driven candidate sets;
    treat VIF thresholds as heuristics (Fieberg & Johnson 2015).

## Routing to reference files

Read the relevant reference before writing path-specific code.

Core (annotate → diagnose → fit):
- `references/covariate_annotation.md` — extract/join covariates onto points on
  any schema; per-layer reprojection; comparing two covariate products.
- `references/covariate_palette.md` — light, source-cited starting menu by system;
  a menu to choose from, not a prescription.
- `references/selection_diagnostics.md` — used-vs-available histograms and w(x)
  selection-ratio plots, before and after modeling.

Fitting:
- `references/fit_clogit_and_model_selection.md` — `survival::clogit` + a
  model-selection loop (LRT, AIC, VIF/correlation, forest plots) with method
  cautions.
- `references/mixed_issf_glmmtmb.md` — multi-individual mixed iSSF, Poisson trick,
  random slopes, per-individual kernel updates.
- `references/incomplete_data.md` — missing fixes, forgiveness, dynamic+model,
  multistep.
- `references/smooth_issf_mgcv.md` — smooths, random effects, spatial & varying
  coefficients.

Method / interpretation:
- `references/movement_kernel_corrections.md` — all-distribution corrections.
- `references/goodness_of_fit.md` — UHC plots + lineup protocol.
- `references/simulation_ud.md` — redistribution kernels, transient/steady-state
  UDs.
- `references/interpretation_rss.md` — log-RSS, reference-level traps, scale
  dependence.

## Key references (for grounding, not to reproduce verbatim)

Avgar et al. 2016 (iSSA foundation); Fieberg et al. 2021 (interpretation, App C);
Michelot et al. 2024 (model vs. inference); Klappstein et al. 2024 (mgcv smooths &
random effects); Chatterjee et al. 2024 + Muff et al. 2020 (mixed iSSA); Signer et
al. 2024 (simulation/UD); Fieberg, Freeman & Signer 2024 (lineups/GOF); Hofmann et
al. 2024 (incomplete data); Fieberg & Johnson 2015 (model-selection caution).
