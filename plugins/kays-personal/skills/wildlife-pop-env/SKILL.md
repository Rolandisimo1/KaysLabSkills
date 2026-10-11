---
name: wildlife-pop-env
description: Activate the wildlife population-biology R stack (unmarked, secr, nimble, nimbleEcology, spOccupancy, amt, Distance, marked, popbio, MCMCvis) in the `wildlife-pop` conda environment. Use at the START of any R session that fits occupancy, N-mixture, spatial capture-recapture, distance-sampling, mark-recapture, step-selection, or matrix population models. The packages live in a workspace R library that must be restored and put on .libPaths() first, and NIMBLE needs its compile directory redirected, so `library(unmarked)` or `compileNimble()` fail without this setup. Triggers: occupancy model, N-mixture, secr density, distance sampling, CJS/mark-recapture, PVA, integrated population model, NIMBLE compile error, "there is no package called", "Refusing to dyn.load shared library".
---

# wildlife-pop environment

R environment `wildlife-pop` (R 4.5.3). Conda supplies the spatial/GLMM stack;
the ten wildlife packages are **not on conda-forge** and were built from source
into a **workspace** R library. Two sandbox constraints drive everything below.

## The two constraints

1. **Compiled `.so` files load only from the workspace R library.** The sandbox
   refuses `dyn.load` from a host-granted path (`/Users/rwkays/...`) with
   `Refusing to dyn.load shared library from writable path`. So the library
   lives at `./.r-libs/wildlife-pop`, and because the workspace is swept
   between sessions it is archived as the artifact `wildlife_pop_rlib.tar.gz`.
2. **The conda prefix library is read-only.** Never `install.packages()` into
   `$CONDA_PREFIX/lib/R/library`; it silently fails.

## Session setup (do this first, in order)

**Step 1 — restore the library** (`python` cell, env `wildlife-pop`; this skill's
sidecar is already loaded):

```python
print(wildlife_r_setup(host))   # {'status': 'restored'|'present', 'n_packages': 75}
```

**Step 2 — first line of the first `r` cell:**

```r
.libPaths(c(normalizePath("./.r-libs/wildlife-pop"),
            file.path(Sys.getenv("CONDA_PREFIX"), "lib/R/library")))
```

Set once per kernel; re-set after any kernel restart. Skipping it gives
`there is no package called 'unmarked'` even though it is installed.

## NIMBLE: redirect the compile directory

NIMBLE compiles C++ and `dyn.load`s it. Its default target is R's `tempdir()`,
which the sandbox refuses. Pass `dirName` pointing **inside the R library** on
every compile call:

```r
NIMBUILD <- file.path(normalizePath("./.r-libs/wildlife-pop"), "nimble_scratch")
dir.create(NIMBUILD, showWarnings = FALSE)

m      <- nimbleModel(code, data = ..., constants = ..., inits = ...)
cm     <- compileNimble(m, dirName = NIMBUILD)
cmcmc  <- compileNimble(buildMCMC(m), project = m, dirName = NIMBUILD)
samples <- runMCMC(cmcmc, niter = ..., nburnin = ...)
```

`nimbleMCMC()` (the one-call wrapper) has **no `dirName` argument** and will
fail — use the explicit `nimbleModel` → `buildMCMC` → `compileNimble` →
`runMCMC` sequence above. Delete `nimble_scratch` before re-archiving the
library.

## What is where

| Source | Packages |
|---|---|
| conda prefix (read-only) | tidyverse, ggplot2, sf, terra, raster, sp, spatstat, mgcv, glmmTMB, DHARMa, lme4, coda, suncalc, Rcpp/RcppArmadillo/RcppEigen, compilers, make, cmake, gsl, gmp, mpfr |
| workspace R library | unmarked 1.5.2, secr 5.4.3, nimble 1.4.3, nimbleEcology 0.5.0, spOccupancy 0.8.1, amt 0.3.1.0, Distance 2.0.1, marked 1.2.8, popbio 2.8, MCMCvis 0.16.5, + 65 deps (rstan, ctmm, mrds, spAbundance, RcppParallel, …) |

Verified by parameter recovery: `occu` psi 0.63/p 0.40 (true 0.60/0.40); `secr`
D-hat 5.22 (SE 0.69, true 5); NIMBLE p 0.34 (true 0.30); `spOccupancy` psi
0.49/p 0.36 (true 0.50/0.35); popbio lambda 1.2494; Distance minke N 15,835.

## Adding a package

Install into the workspace library with **only that library and the conda
prefix on the path** — otherwise R sees a stale host library and skips builds:

```r
WS <- normalizePath("./.r-libs/wildlife-pop")
.libPaths(c(WS, file.path(Sys.getenv("CONDA_PREFIX"), "lib/R/library")))
install.packages("newpkg", lib = WS, repos = "https://cloud.r-project.org",
                 dependencies = c("Depends","Imports","LinkingTo"),
                 INSTALL_opts = c("--no-docs","--no-html"))
```

Then re-archive so the addition survives the next session:

```bash
rm -rf .r-libs/wildlife-pop/nimble_scratch
tar -czf wildlife_pop_rlib.tar.gz -C .r-libs wildlife-pop
```

and `save_artifacts(["wildlife_pop_rlib.tar.gz"], version_of={...})` onto the
existing artifact.

**Build-dependency gotchas already solved** (system libs are in the conda env;
these are the failures to recognize if a new package needs them): RcppParallel
needs `cmake`; `gmp`/`Rmpfr` need `--with-gmp-include=$CONDA_PREFIX/include`
and `--with-gmp-lib=$CONDA_PREFIX/lib` via `configure.args`.

RMark is deliberately absent — it shells out to a separate MARK binary. Use
`marked` or NIMBLE for mark-recapture instead.
