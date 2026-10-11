# Software environments on Hazel

## Modules (system software)

```bash
module avail            # list everything
module load R           # system R
module load conda       # staff-maintained conda / Python 3
module load cuda        # CUDA toolkit for GPU code
module list             # what's loaded
module purge            # clean slate
```

Load modules inside batch scripts, not just interactively — batch jobs start
with a fresh environment.

## Conda: one-time setup (do this before anything else)

Users hit two mandatory setup steps. Skipping the `.condarc` step is the #1
way people blow their 15 GB home quota.

1. Initialize conda (once per account):
   ```bash
   module load conda
   conda init bash
   # log out and back in
   ```
2. Create `~/.condarc` pointing the package cache at /share and adding common
   channels:
   ```yaml
   pkgs_dirs:
     - /share/GROUPNAME/UNITYID/conda/pkgs
   channels:
     - conda-forge
     - bioconda
     - defaults
   ```

Also relocate the pip cache off home (same quota problem):
`pip config set global.cache-dir /share/GROUPNAME/UNITYID/.pip_cache` or set
`PIP_CACHE_DIR`.

## Where environments live

Conda environments go in the project software space, **not** home:

```bash
conda env create --prefix /usr/local/usrapps/GROUPNAME/UNITYID/env_name -f env.yml
conda activate /usr/local/usrapps/GROUPNAME/UNITYID/env_name
```

- `/usr/local/usrapps/GROUPNAME` must be requested from HPC staff if it
  doesn't exist yet (see the HPC software page). Quota: 100 GB / 250K files.
- Installs run on **login nodes only**: compute nodes have no internet and
  cannot write to /usr/local/usrapps.
- Data never goes in /usr/local/usrapps and jobs are never run from there —
  compute nodes mount it read-only.

## Use YAML files, don't grow environments

`conda install` into an existing environment routinely breaks it ("solving
environment" hangs, then conflicts). The reliable pattern:

1. Write a YAML file listing everything the workflow needs:
   ```yaml
   name: env_torch
   channels:
     - conda-forge
   dependencies:
     - python=3.11
     - pytorch
     - torchvision
     - numpy
     - pandas
     - notebook        # include if Jupyter is needed
   ```
2. `conda env create --prefix ... -f env.yml`
3. Need a new package later? Create a **new** environment with an updated
   YAML; keep the old one until the new one is tested.

Pip-only packages: put all conda-available dependencies in the YAML (include
`pip`), create and activate the environment, then `pip install` the rest.

## R packages

Two routes; don't mix them in one workflow:

**System R + install.packages** — fine for pure-R packages.
- Install from a login node (compute nodes have no internet).
- Let R create its default local library on first install. Custom location:
  put `R_LIBS=~/libs/R_libs` in `~/.Renviron`.
- Don't run R with `--vanilla` in jobs, or user libraries won't be found.

**Conda R** — better when packages have heavy system dependencies (sf, terra,
rstan, Bioconductor stacks). Conda packages are typically named
`r-packagename`.
- Conda installs its *own* R. When using a conda R environment: do **not**
  `module load R`, and remove `~/.Renviron`, otherwise the two installations
  cross-contaminate library paths and produce baffling load errors.
- Packages missing from conda: activate the environment and use
  `install.packages()` inside it.
- Bioconductor: fresh conda env with recent `r-base`, then BiocManager inside
  it.

## Known traps

- Batch scripts must `source ~/.bashrc` before `conda activate`.
- Conda-installed MPI (in mpi4py, Rmpi, some domain codes) will not work with
  Slurm. Build against system MPI: `module load PrgEnv-intel` (or
  openmpi-gcc), then `pip install mpi4py` / compile Rmpi.
- Many conda applications auto-detect all cores on a node and oversubscribe.
  Pin thread counts (`OMP_NUM_THREADS`, `MKL_NUM_THREADS`,
  `OPENBLAS_NUM_THREADS` = `$SLURM_CPUS_PER_TASK`) or use `--exclusive`.
- Apptainer is available for containerized applications; a container is often
  the fastest route for tools with impossible dependency stacks.
