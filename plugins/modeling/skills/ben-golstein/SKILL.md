---
name: ben-golstein
description: >-
  Build and analyze hierarchical ecological models in R the way Ben Goldstein
  (dochvam) does. Use for occupancy, N-mixture, abundance, and species-distribution
  models; integrated SDMs that fuse camera traps, iNaturalist, eBird, telemetry, and
  spatial covariates; NIMBLE / nimbleEcology model code; simulation-based validation
  of an estimator; and structuring a reproducible-analysis repo for a manuscript.
  Triggers: "occupancy model", "N-mixture", "integrated SDM / data integration",
  "camera trap detection histories", "iNaturalist bias", "NIMBLE", "simulation study",
  "reproducible code for a paper".
---

# Hierarchical Ecology Modeling (style: Goldstein)

Extracted from Mammal_SVCs_ISDM_reproducible, Red_Snapper_ESA,
autocorr_occ_camtraps_reproducible, and iNat_novelty_specialization_reproducible.
The through-line: hierarchical statistical models fit to messy, semi-structured
biodiversity data, integrated across sources, and always validated against
simulation from known truth — packaged so a reviewer can reproduce every figure.

## Tooling defaults

- R throughout, organized as an `.Rproj`.
- NIMBLE for custom hierarchical models, with nimbleEcology (e.g. dHMM,
  occupancy/N-mixture distributions) and nimbleSMC where needed. unmarked +
  AICcmodavg for standard likelihood occupancy models and GOF.
- dplyr (`%>%`, `count`, `mutate`, `bind_rows`) for the data/summary layer.
- For custom likelihoods, plain optim MLE: `control = list(fnscale = -1)` to
  maximize, a BFGS re-optimization pass with `hessian = TRUE`, and SEs from
  `sqrt(diag(solve(-hessian)))` wrapped in `tryCatch`.
- Work on the logit/expit scale for probabilities; keep a named parameter vector
  and a matching parnames vector.

## Reproducible-analysis repo layout

Structure every manuscript repo so it runs top to bottom:

- Numbered entry-point scripts run in order — either at root (`00_*.R`, `01_*.R`, …)
  or in a `code_main/` dir numbered 1–5. Prefix encodes run order.
- Helper dirs of functions that are never run directly: `helper_code/`,
  `code_helper/`, or `setup_code/`. Sourced at the top of entry scripts
  (`source('code_helper/gof.R')`).
- Split by workflow: `code_casestudy/` (real data), `code_simulations/` /
  `validation_sim/` (the simulation study), `code_main*/` for parallel model
  variants (e.g. `main_code_lineage/` vs `main_code_nolineage/`).
- Data & output dirs: `input_data/` (raw, e.g. from the iNaturalist export tool),
  `intermediate/` (empty in the repo, catches generated files), `plots/`,
  `results_tables/` (committed outputs so others don't have to re-run week-long fits).
- A `necessary_packages.R` that just loads everything, so users can check their environment.
- Big data lives on Zenodo with a DOI, not in Git; the README says exactly which
  Zenodo subdir unzips into which local dir, and the archive carries its own
  README.txt describing each file.
- Per-subdirectory README.md files, plus a top README that (a) lists each numbered
  script and what it does and (b) explains data retrieval. Credit any adapted code
  with a link (e.g. Augustine's UnmarkedSCR).

## Code style inside files

- File starts with a banner header block: filename + one-paragraph purpose.
- Every function carries a roxygen-style block: `#' @name`, `#' @param` for each
  argument, `#' @description`. This holds even for internal helpers in a script.
- Naming is descriptive snake_case: `sim_occu_clustered`, `fit_cluster_occ_mod`,
  `sim_and_evaluate_one_mod`, with a thin `_par` wrapper whose only job is to make
  parallelization clean.
- expit/logit helpers used everywhere; HMM/state-space formulations built from
  explicit observation and transition matrices.

## Simulation-based validation is a first-class deliverable

Never ship an estimator without a simulation study. The pattern:

- Define a `design_df` — one row per simulation scenario (sample size, detection
  prob, autocorrelation strength, window/gap, etc.), crossed with iterations.
- For each row: simulate data from known true parameters, fit every candidate model,
  and also simulate an out-of-sample replicate.
- Evaluate with a fixed set of metrics returned as tidy data frames:
  - absolute error (estimate − truth),
  - CI coverage (does the 95% interval, est ± 1.96·SE, contain the true value?),
  - RMSE in-sample and out-of-sample,
  - goodness-of-fit p-values (e.g. a join-count test for spatial/serial dependence).
- Parallelize across `design_df` rows; wrap each run in `tryCatch` so one failure
  returns an "Errored" summary row instead of killing the batch. State the core count
  explicitly and expect runs to take days.
- Validation sims should reuse the real dataset to generate realistic
  abundance/covariate patterns rather than idealized ones.

## Data integration (ISDM) philosophy

The signature move is fusing heterogeneous, imperfect datasets into one joint model
rather than analyzing each alone:

- Combine e.g. iNaturalist counts + camera-trap detection histories + spatial
  covariates (Mammal SVCs), or baited-camera + ROV surveys + acoustic-telemetry
  movement (Red Snapper ESA), each with its own observation submodel feeding a shared
  latent ecological process.
- Always ask whether integration actually helps (`join_or_not_join`): quantify how an
  estimate (e.g. effective sampling area, a niche parameter) shifts when you drop each
  auxiliary dataset. Make that ablation a figure.
- Treat detection/reporting as an explicit, modeled process. Much of the work is
  characterizing bias in citizen-science data — novelty/favoritism bias,
  over/under-reporting, autocorrelated detections — and building the observation model
  to absorb it.

## Camera-trap specifics

- Detection histories as site × occasion matrices; be deliberate about the detection
  window and gap used to aggregate raw triggers, and test the estimator's sensitivity
  to that choice (autocorrelated triggers bias naive occupancy).
- SnapshotUSA is a common real-data source for case studies.
- For abundance from unmarked cameras, spatial capture-recapture (USCR) formulations
  in NIMBLE.

## Checklist when starting an analysis in this style

- `.Rproj` + numbered entry scripts + helper dir of documented functions.
- `input_data/` / `intermediate/` / `plots/` / `results_tables/`; big data to Zenodo
  with a DOI.
- Roxygen block on every function; banner header on every file.
- A simulation study with a `design_df`, abs-error / coverage / RMSE, parallel + tryCatch.
- If integrating datasets: an explicit observation submodel per source and a drop-one ablation.
- Model the detection/reporting bias, don't ignore it.
