# Troubleshooting jobs on Hazel

## First moves for any failed or finished job

```bash
sacct -j JOBID --format=JobID,JobName,State,ExitCode,Elapsed,MaxRSS,ReqMem,AllocCPUS
seff JOBID        # efficiency summary: CPU% and memory used vs requested
```

Then read the job's `err.%j` / `out.%j` files. The combination of Slurm state
+ stderr almost always identifies the problem.

## Decoding common failures

| Symptom | Likely cause | Fix |
|---|---|---|
| State `OUT_OF_MEMORY`, or killed with `oom-kill` in stderr | Job exceeded `--mem` | Check MaxRSS in sacct; raise `--mem`, or use `--exclusive` for unpredictable memory (big rasters, genomics). |
| State `TIMEOUT` | Hit `--time` limit | Raise the limit (partitions allow up to ~4 days), checkpoint, or split into a job array. |
| `CANCELLED` shortly after start, or killed while interactive | Ran on a login node, or idle interactive session reaped | Confirm with `hostname`; move work into sbatch. |
| `conda: command not found` / activate fails in batch | Missing shell hooks | Add `source ~/.bashrc` before `conda activate`. |
| R can't find installed packages in batch | `--vanilla` flag, wrong `~/.Renviron`, or conda-R/system-R mix | Drop `--vanilla`; if using conda R, remove `~/.Renviron` and don't `module load R`. |
| `Disk quota exceeded` | Home quota (15 GB / 10K files), often from conda/pip caches | `quota_display`; move caches to /share (see environments.md); keep data in /share. |
| Input files vanished | 30-day scratch purge on /share | Files unused 30 days are deleted; re-stage and keep master copies elsewhere. |
| Job much slower than expected, CPU% in seff ≫ 100% per core or node overloaded | Library spawned threads for every core on the node | Set `OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK` (and MKL/OPENBLAS equivalents), or `--exclusive`. |
| GPU job fails with no CUDA device | Missing/incomplete `--gres` | Must be `--gres=gpu:TYPE:N` with an explicit type, plus `--partition=gpu`. |
| MPI job runs all ranks on one node or crashes at init | conda-installed MPI | Rebuild mpi4py/Rmpi against system MPI module. |
| Cannot write output under /usr/local/usrapps | By design — compute nodes mount it read-only | Write to /share; usrapps is for software only. |

## Pending jobs

```bash
squeue -u $USER                 # ST column: PD = pending
squeue -j JOBID -o "%.18i %.9P %.8j %.8u %.2t %.10M %.6D %R"   # %R = reason
```

Common reasons: `Priority`/`Resources` (normal queueing — big memory,
exclusive, and popular-GPU requests wait longest), `QOSMaxJobsPerUser` style
limits, or an impossible request (e.g. more memory than any node has — job
pends forever). Requesting the scarce GPUs (a100/h100/h200) can mean long
waits; a smaller GPU type often dispatches much sooner. Right-sizing `--time`
and `--mem` downward improves backfill chances.

## Checking a running job

```bash
squeue -u $USER                        # state, elapsed, node
sstat -j JOBID --format=JobID,MaxRSS   # live memory of running job
```

For a deeper look, note the node from squeue and (briefly) `ssh` to it while
the job runs, then `top -u $USER`.

## After fixing: verify efficiency

Run `seff JOBID` on the successful job. If memory used is far below `--mem`
or CPU efficiency is low, trim the request — smaller requests queue faster
and are better cluster citizenship. This is a good habit to suggest
proactively.

## Getting help

Cluster status page for outages: https://hpc.ncsu.edu (Cluster Status).
Help tickets and consultations via the Contact page. Include the job ID,
batch script, and error file in tickets.
