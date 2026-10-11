# LSF → Slurm translation for Hazel

Hazel ran LSF before migrating to Slurm. Old scripts, lab wikis, and even
current pages on hpc.ncsu.edu (R, Python, Conda application pages) still show
LSF syntax. Translate on sight — LSF commands do not exist on Hazel anymore.

## Directives

| LSF | Slurm | Meaning |
|---|---|---|
| `#BSUB -J name` | `#SBATCH --job-name=name` | job name |
| `#BSUB -W 120` or `-W 2:00` | `#SBATCH --time=02:00:00` | walltime (LSF minutes or H:MM → Slurm HH:MM:SS) |
| `#BSUB -n 8` | `#SBATCH --ntasks=8` (MPI) or `--ntasks=1 --cpus-per-task=8` (threaded) | cores |
| `#BSUB -R "span[hosts=1]"` | `#SBATCH --nodes=1` | all cores on one node |
| `#BSUB -R "rusage[mem=64GB]"` | `#SBATCH --mem=64G` | memory |
| `#BSUB -x` | `#SBATCH --exclusive` | whole node |
| `#BSUB -o out.%J` | `#SBATCH --output=out.%j` | stdout (`%J`→`%j`) |
| `#BSUB -e err.%J` | `#SBATCH --error=err.%j` | stderr |
| `#BSUB -q queue_name` | `#SBATCH --partition=name` | queue → partition |
| `#BSUB -R "select[gpu]"` / gpu queue | `#SBATCH --partition=gpu --gres=gpu:TYPE:N` | GPUs (type required) |

## Commands

| LSF | Slurm |
|---|---|
| `bsub < script.sh` | `sbatch script.sh` (no `<`) |
| `bsub -Is -n 4 -W 30 bash` | `salloc --ntasks=4 --nodes=1 --time=00:30:00` |
| `bjobs` | `squeue -u $USER` |
| `bjobs -l JOBID` | `sacct -j JOBID` / `squeue -j JOBID -l` |
| `bkill JOBID` | `scancel JOBID` |
| `bqueues` | `sinfo` |
| `bpeek JOBID` | `tail -f out.JOBID` (output streams to file) |
| `mpirun ./code` | `srun ./code` |

## Translation gotchas

- LSF `-n 8` for a *threaded* (non-MPI) program becomes
  `--ntasks=1 --cpus-per-task=8`, not `--ntasks=8`. Getting this wrong makes
  Slurm think there are 8 separate tasks and thread-pinning breaks.
- LSF `-W` takes minutes (`-W 120`) or hours:minutes (`-W 2:00`); Slurm
  `--time` is `HH:MM:SS` or `D-HH:MM:SS`.
- `bsub` reads the script from stdin (`bsub < job.sh`); `sbatch` takes it as
  an argument. Users copying old habits often type `sbatch < job.sh` — works,
  but plain `sbatch job.sh` is the norm.
- `%J` in LSF output filenames is `%j` in Slurm; array jobs use `%A_%a`.
- LSF environment variables map too: `$LSB_JOBID` → `$SLURM_JOB_ID`,
  `$LSB_JOBINDEX` → `$SLURM_ARRAY_TASK_ID`, `$LSB_DJOB_NUMPROC` →
  `$SLURM_NTASKS`.
