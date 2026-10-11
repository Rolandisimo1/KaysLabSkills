# Hazel batch script templates

All templates assume the user's Unity ID group is `$GROUP` (first entry in
`groups` output) and that job data lives in `/share/$GROUP/$USER`. Fill in
real values rather than leaving shell variables in #SBATCH lines — Slurm does
not expand variables inside directives.

## Serial R job (system R)

```bash
#!/bin/bash
#SBATCH --job-name=rmodel
#SBATCH --output=out.%j
#SBATCH --error=err.%j
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=02:00:00
#SBATCH --mem=16G

module load R
Rscript my_program.R
```

## Multicore R job

R parallelism (parallel, foreach/doParallel, future, data.table) is
shared-memory: it cannot cross nodes. Request cores on one node and tell R
how many it actually has — many R libraries otherwise spawn one thread per
physical core on the node.

```bash
#!/bin/bash
#SBATCH --job-name=rpar
#SBATCH --output=out.%j
#SBATCH --error=err.%j
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=06:00:00

module load R
export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK
Rscript models.R
```

In the R code, size worker pools from the allocation, e.g.
`ncores <- as.integer(Sys.getenv("SLURM_CPUS_PER_TASK", "1"))`.

Memory-hungry R work (rasters, GeoTIFFs, large genomics objects) that can't
be sized precisely: request `--exclusive` to get the whole node and its
memory.

## Python job with conda environment

```bash
#!/bin/bash
#SBATCH --job-name=pyjob
#SBATCH --output=out.%j
#SBATCH --error=err.%j
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=04:00:00

source ~/.bashrc                # required before conda activate in batch
conda activate /usr/local/usrapps/GROUPNAME/UNITYID/env_name
python my_script.py
conda deactivate
```

The `source ~/.bashrc` line is mandatory — without it `conda activate` fails
in batch because the conda shell hooks aren't loaded.

## GPU job (e.g. PyTorch training on an A100)

```bash
#!/bin/bash
#SBATCH --job-name=train
#SBATCH --output=out.%j
#SBATCH --error=err.%j
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a100:1

source ~/.bashrc
conda activate /usr/local/usrapps/GROUPNAME/UNITYID/env_torch
python train.py
```

- GPU **type is required** in `--gres`. Types on Hazel: a10, a30, a100,
  gtx1080, h100, h200, l40, l40s, p100, rtx_2080. Pick the cheapest GPU that
  fits the model — A100/H100/H200 queues are the busiest.
- PyTorch/TensorFlow from conda-forge bundle their own CUDA runtime, so
  `module load cuda` is usually only needed for code you compile yourself.
- Verify inside the job: `python -c "import torch; print(torch.cuda.get_device_name(0))"`.

## Job array (many similar runs, e.g. per-scenario R fits)

```bash
#!/bin/bash
#SBATCH --job-name=sweep
#SBATCH --output=out.%A_%a
#SBATCH --error=err.%A_%a
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --time=02:00:00
#SBATCH --mem=8G
#SBATCH --array=1-100

module load R
Rscript fit_one.R $SLURM_ARRAY_TASK_ID
```

The script receives the task index (1–100) as an argument; use it to pick a
parameter row. `%A` is the array job ID, `%a` the task index. Arrays are much
kinder to the scheduler than a loop of `sbatch` calls.

## Interactive session

```bash
salloc --nodes=1 --ntasks=4 --time=00:30:00
# GPU:
salloc --nodes=1 --ntasks=1 --partition=gpu --gres=gpu:a100:1 --time=00:30:00
```

Once dispatched you get a shell on a compute node. Use for debugging only;
production work belongs in batch scripts. Idle sessions get terminated.

## Jupyter notebook on a compute node

1. On Hazel: `salloc --nodes=1 --ntasks=4 --time=04:00:00`, note the compute
   node name (e.g. `c123n01`).
2. In the session:
   ```bash
   source ~/.bashrc
   conda activate /usr/local/usrapps/GROUPNAME/UNITYID/env_name   # env must include 'notebook'
   jupyter notebook --no-browser --port=1113 --ip=0.0.0.0
   ```
   Copy the URL with the token.
3. On the local machine, tunnel through a login node:
   ```bash
   ssh -N -L 1112:c123n01:1113 unityID@login.hpc.ncsu.edu
   ```
4. Open the token URL in a browser with the host part replaced by
   `localhost:1112`.
5. Done: Quit in Jupyter, `exit` the salloc session, Ctrl+C the tunnel.

## MPI job (rare for R/Python users)

```bash
#!/bin/bash
#SBATCH --job-name=mpijob
#SBATCH --output=out.%j
#SBATCH --error=err.%j
#SBATCH --ntasks=32
#SBATCH --time=02:00:00

module load PrgEnv-intel      # or openmpi-gcc
srun ./my_mpi_code.exe
```

Launch MPI programs with `srun`. Rmpi and mpi4py must be built against the
system MPI (load the MPI module, then `pip install mpi4py` /
install Rmpi from source) — conda-installed MPI will not talk to Slurm.
Rmpi jobs launch with a single task spawning the rest:
`mpirun -n 1 Rscript script.R`.
