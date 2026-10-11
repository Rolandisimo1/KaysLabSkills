---
name: sdm-paper-verification
description: "Empirically verify methods critiques of a species distribution modeling (SDM/ENM/Maxent) paper from its data deposit. Use when the user provides a paper plus its Dryad/Zenodo code-and-data archive and wants claims checked, re-analyzed, or re-fitted rather than just reviewed - e.g. sampling-bias/target-group background design, predictor collinearity and variable-importance comparisons, cross-species significance tests ignoring phylogeny, or a corrected re-fit of all models. Triggers: \"verify this critique\", \"check this paper's methods\", \"re-run with corrected bias correction\", \"is this SDM result an artifact\"."
---

# SDM paper verification from a data deposit

Workflow for checking methods critiques of a presence-background SDM paper
against its own deposited code and data, and re-fitting corrected models.
Developed on Chen et al. 2026 (J. Biogeography, 219 North American mammals);
generalizes to any Maxent/maxnet-style multi-species importance study.

## Order of operations

1. **Reproduce before you critique.** From the deposit's fitted outputs
   (e.g. per-species `maxentResults.csv`), reproduce the paper's headline
   numbers exactly (top-predictor percentages, mean importances, published
   p-values). If you can't reproduce, stop and diagnose. Reproducing the
   published p-values also reveals the *actual* test used - e.g. a caption
   saying "Wilcoxon signed-rank" (paired) may only reproduce with
   `pairwise_wilcox_test(paired=FALSE)` (unpaired Mann-Whitney). Check with
   both statsmodels/scipy: unpaired MWU over all variable pairs + Hommel is
   the rstatix default pipeline.

2. **Reverse-engineer the background/bias design from the points** (the
   generation script is often missing from deposits). Three diagnostics:
   - **Shared coordinates between overlapping species**: near-zero sharing
     of exact background coords means independent per-species draws, not one
     clipped continental surface.
   - **Pairwise density-difference correlation**: for range-overlapping
     species pairs, correlate (log bg-density A - log bg-density B) with
     (log own-occurrence-KDE A - log own-occurrence-KDE B) on a coarse
     (~50 km) grid. r >> 0 across all pairs = backgrounds track each
     species' OWN records (self-KDE, non-standard); r ~ 0 = pooled
     target-group surface (standard).
   - **Poisson regression of background counts on both candidate surfaces**
     (own KDE vs pooled-minus-focal KDE) - the larger weight names the design.
   - Also compare the effort covariate (human footprint etc.) at
     occurrences vs backgrounds vs uniform-random domain points: backgrounds
     sitting near uniform means the bias correction never engaged the
     gradient that matters.

3. **Collinearity audit.** Sample ~200k random valid raster cells; full
   correlation matrix. Check whether a stated |r| threshold was applied to
   ALL predictors or only one block. Fragmentation test: compare the focal
   variable's importance vs (a) best single competitor, (b) block-sums.
   Note both caveats: block-sums over correlated variables double-count
   shared signal, and a composite index vs single variables is partly
   intrinsic to the question.

4. **Non-independence corrections** for cross-species tests:
   - Cluster bootstrap (resample genera/orders/spatial blocks of range
     centroids, 20k draws, percentile CIs).
   - Phylogenetic GLS intercept-only on the per-species paired difference,
     `nlme::gls` + `ape::corPagel` (fallback corBrownian), REML, over ~100
     trees; resolve tip synonyms (Clethrionomys->Myodes etc.) before
     matching. Report lambda and the median p across trees.

5. **Corrected re-fit** (the decisive step):
   - Build pooled target-group backgrounds: 10-km occurrence-count surface
     of ALL deposited species MINUS the focal species, Gaussian-smooth
     (sigma ~30 km), sample 10k points within each species' modelling
     domain, place at random 1-km subcells restricted to valid predictor
     cells.
   - Fit with `maxnet` (classes="lq" to match linear+quadratic papers,
     default regularization). Permutation importance = mean training-AUC
     drop over 2+ permutations of each variable, normalized to sum to 100.
   - **Always run an estimator control**: same maxnet pipeline on the
     AUTHORS' original backgrounds. If the control reproduces the paper,
     every subsequent change is attributable to your intervention, not the
     estimator switch. Report the control alongside.
   - Run both covariate spaces: raw predictors AND the orthogonalized space
     (PCA of the full bioclim stack from ~100k random cells - verify
     cumulative variance matches the paper's supplement - plus the
     non-climate block).
   - Parallelize: shard species across cores with a standalone Rscript
     (nohup loop + wait); ~1 min/species for 10k bg points with maxnet lq.

6. **Stack all fixes** and report the cascade: published -> +effort fix ->
   +orthogonal axes -> +phylogenetic correction, for the paper's marquee
   contrast. Single-vs-single framings can partially offset across stages
   (raw temperature near-duplicates make the "best single climate variable"
   strong; PCs dilute it) - the block-level comparison is the fair summary.

## Pitfalls learned the hard way

- Deposited RData files can be huge (>1 GB); extract selectively from the
  zip rather than unpacking everything.
- Different rasters in one deposit may sit on different grids (a 19-band
  bioclim stack vs the modelling grid); extract per-raster with its own
  transform, never assume alignment.
- Species with sparse coverage on a secondary grid fail complete-case
  filters only for one covariate set - handle each set's failure
  independently rather than dropping the species.
- rstatix p-values in figure captions are often pasted into `tribble()`
  calls in the plotting code - grep for those to find the exact published
  values to reproduce.
- Phylogeny tip names lag taxonomy; keep a small synonym map and report
  how many species matched.

## Reporting

Verdict per critique (supported / partial / not supported), with the
reproduced-numbers table up front, an estimator-control table for any
re-fit, and explicit caveats in both directions (what tempers the critique,
not just what confirms it). Keep the distinction between "the effect
direction survives" and "the significance/headline survives" - they often
diverge.
