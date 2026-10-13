---
name: hazel-hpc
description: >-
  Work with the Hazel supercomputing cluster at NC State University (NCSU HPC).
  Use this skill whenever the user mentions Hazel, NCSU HPC, hpc.ncsu.edu, or
  asks about anything they will run on the university cluster: writing or
  fixing sbatch/Slurm batch scripts, requesting GPUs (A100/H100/etc.), setting
  up conda environments or R packages on the cluster, running Python/ML or R
  jobs, Jupyter on a compute node, storage and quota questions (/share, home
  directory, usrapps), interactive sessions, or diagnosing failed, killed, or
  pending jobs. Also use it when the user pastes an old LSF/#BSUB script from
  the NCSU docs that needs translating to Slurm.
metadata:
  authored_via: "claude-science"
  published_by: "agent"
  published_at: "2026-09-17T19:01:25.308Z"
  authored_by: "unknown"
  last_modified_by: "agent"
  last_modified_at: "2026-09-17T19:01:25.304Z"
---

# Hazel HPC Cluster (NC State University)

Hazel is NCSU's shared Linux cluster: ~400 nodes, 14,000+ cores, Intel Xeon
and AMD EPYC, some nodes with GPUs. Scheduler is **Slurm**. Login via
`ssh unityID@login.hpc.ncsu.edu` or Open OnDemand at
https://servood.hpc.ncsu.edu (Clusters → Hazel Shell Access).

## Critical rule: many official Hazel docs are outdated

Hazel migrated from LSF to Slurm, but several pages on hpc.ncsu.edu (notably
the R, Python, and Conda application pages) still show old LSF syntax:
`#BSUB` directives, `bsub < script`, `bjobs`, `-R "span[hosts=1]"`. **Never
reproduce LSF syntax** — it will not work. If the user pastes such an example,
translate it using `references/lsf-to-slurm.md`. Everything must be `#SBATCH`
directives submitted with `sbatch script.sh`.

## Non-negotiable cluster rules

These come from Hazel's Acceptable Use Policy and cause real breakage or
account trouble if violated, so bake them into every script and instruction:

- **Never run computation on a login node.** Login nodes are for editing,
  compiling, package installation, and job submission only. Anything else goes
  through `sbatch` or an interactive `salloc` session. Check with `hostname` —
  if it says `login0x`, don't run the workload there.
- **Submit jobs from `/share/$GROUP/$USER`**, not from home. Home has a 15 GB
  / 10,000-file quota; jobs should read and write under /share.
- **Package installs happen on login nodes only.** Compute nodes have no
  internet access and cannot write to `/usr/local/usrapps`.
- **/share is scratch**: not backed up, files unused for 30 days are deleted.
  Remind users to copy results they care about off the cluster or to backed-up
  storage.
- **Never SSH directly to a compute node** (e.g. `ssh c207n06`). All compute-node
  access must go through the scheduler. HPC staff actively monitor for this and
  send policy-violation warnings for it — repeated violations can get an
  account's HPC access disabled. If you need a live shell on a node where a job
  is already running (e.g. to check resource usage or debug a stuck process),
  use `srun --jobid=<jobid> --overlap --nodelist=<node> --pty /bin/bash`. For
  routine monitoring, `squeue`, `sacct`, and `sstat --format=JobID,MaxRSS,AveRSS
  -j <jobid>.batch` from the login node cover almost everything without needing
  node access at all.

## Storage map

| Path | Quota | Purpose | Notes |
|---|---|---|---|
| `/home/$USER` | 15 GB, 10K files | scripts, small code | backed up daily |
| `/share/$GROUP/$USER` | 20 TB, 1M files (per project) | job data, working space | NOT backed up, 30-day purge |
| `/usr/local/usrapps/$GROUP` | 100 GB, 250K files | user-installed software, conda envs | backed up; read-only from compute nodes; must be requested from HPC staff |
| `/gpfs_archive` | 1 TB | instructional mass storage | login nodes only, tape-backed; store as tar archives |

Check quotas with `quota_display`. Find `$GROUP` with `groups` (first group
listed).

## Batch script skeleton (Slurm)

```bash
#!/bin/bash
#SBATCH --job-name=myjob
#SBATCH --output=out.%j
#SBATCH --error=err.%j
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=64G
#SBATCH --time=06:00:00

module load R          # or: source ~/.bashrc && conda activate /usr/local/usrapps/$GROUP/$USER/env_name
Rscript models.R
```

Submit with `sbatch script.sh`. Key points that trip people up:

- R and most Python libraries are **shared-memory only**: always set
  `--nodes=1` for multicore (non-MPI) jobs so cores land on one machine.
- Parallel libraries (data.table, BLAS, PyTorch dataloaders, sklearn) often
  auto-detect **all** cores on the node, not just the allocated ones. Pin
  them: `export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK` (and library-specific
  equivalents), or request `--exclusive`.
- GPU jobs: `--partition=gpu` and `--gres=gpu:TYPE:N` — the **type is
  required**. Available: a10, a30, a100, gtx1080, h100, h200, l40, l40s,
  p100, rtx_2080. `module load cuda` for CUDA codes.
- Interactive testing: `salloc --ntasks=4 --nodes=1 --time=00:30:00`. Keep it
  short; idle sessions get killed.
- Partition time limits run to about 4 days; check `sinfo` for current limits.

Full templates (R, Python/ML, GPU training, job arrays, Jupyter tunneling):
read `references/templates.md`.

## Software environments

System software uses environment modules: `module avail`, `module load R`,
`module load conda`, `module load cuda`. For anything beyond stock R/Python,
Hazel's recommended path is conda environments installed under
`/usr/local/usrapps` — but there is a mandatory one-time setup (`.condarc`
pointing pkgs_dirs at /share, `conda init bash`) and several Hazel-specific
gotchas (batch scripts need `source ~/.bashrc` before `conda activate`; conda
R must not be mixed with `module load R`; MPI packages must build against
system MPI). Before giving any conda, R-package, or pip instructions, read
`references/environments.md`.

## Monitoring and troubleshooting

`squeue -u $USER` (status), `scancel JOBID`, `sacct -j JOBID` (accounting,
exit codes), `seff JOBID` (efficiency — the first thing to check after a job
ends), `sinfo` (partitions). For diagnosing OOM kills, timeouts, stuck-pending
jobs, and conda/R failures in batch, read `references/troubleshooting.md`.

## Cluster-wide status (when YOUR job looks fine but is mysteriously slow)

If a job's own accounting shows normal CPU/memory behavior (no OOM, no
obvious hang) but it's still dramatically slower than an identical past run —
e.g. taking 24h+ on a stage that used to finish same-day, with unchanged code/
env/data/hardware-generation — that points away from your job and toward the
shared cluster itself (filesystem contention, network fabric, an unannounced
change). These are public pages, reachable by a normal HTTPS GET (request
`hpc.ncsu.edu` via `request_network_access` if not already allowlisted):

- **`https://hpc.ncsu.edu/Monitor/news.php`** — HPC current status and planned
  maintenance. Check this FIRST — links to the IT Service Portal for known
  issues, and to live queue-depth charts (10-day jobs plot: total/running/
  pending).
- **`https://hpc.ncsu.edu/Monitor/ClusterStatus.php`** — live utilization by
  interconnect (IB vs 10Gbps), with % utilization and free-core counts. A
  cluster running near-saturated (we saw ~91% IB utilization, ~2,350 jobs
  pending system-wide) is a plausible contributor to I/O-bound stages
  stalling (e.g. NIMBLE's `nimbleModel()` C++ code-generation, which does
  heavy small-file I/O against shared GPFS storage) even when your job's own
  CPU efficiency looks fine.
- **`https://hpc.ncsu.edu/Monitor/hpc_status.php`** — status by node/CPU model.
- **`https://hpc.ncsu.edu/Hazel/`** — planned/recent outage details (e.g. the
  Dec 2025 NFS→GPFS migration for `/home` and `/usr/local` — worth knowing
  this migration happened, since it changed the filesystem serving those
  paths on both login and compute nodes).
- **IT Service Portal for HPC** (linked from `news.php`) — the authoritative
  place for currently-known issues; requires NCSU login, not fetchable
  directly.
- **Two schedulers ran at once during 2026.** Slurm became the production
  scheduler on 17 August 2026 and LSF was retiring at the end of that Fall
  semester, both carrying real load (12 Oct 2026: Slurm 1,611 running / 782
  pending; LSF 1,210 running / 7,125 pending). Worth knowing, but **do not
  reach for it to explain idle nodes.** That inference was made once and
  checked, and it was wrong: the idle capacity was in Slurm's own `compute`
  partition, not on the LSF side.
- **Diagnosing "lots of idle CPUs but our jobs will not start".** Check these
  before forming any theory, and prefer `sinfo`/`scontrol` output over the
  public status pages, whose node counts did not reconcile with Slurm's:
  - `sinfo -R` for drained/down nodes and their stated reasons.
  - `scontrol show reservation --all` for reservations hidden from the default
    listing. In the October 2026 case this returned "No reservations in the
    system", which rules the explanation out rather than confirming it.
  - `scontrol show node <node>` on a node with free CPUs. A state of
    **`MIXED+PLANNED` with no Reason set** means Slurm is holding that node for
    a higher-priority pending job it has already promised a start time to. In
    October 2026, 525 of 557 idle CPUs sat on 78 such nodes.
  - `sacctmgr show qos` for the QOS a job runs under. Caps can block a job from
    capacity that looks free: Hazel's `normal` QOS carried
    `GrpTRES gres/cpu:sapphirerapids=0`, a hard zero on one CPU generation.
    Check whether the held nodes are of a type the job's QOS is barred from.
  - Memory, not just CPUs. A node can show free CPUs while nearly all its
    memory is allocated, so it cannot take the job.
- **Every queued job reporting the SAME `squeue --start` estimate**, whatever
  its wall limit, usually means they are all waiting on the same event rather
  than on a backfill window each could fit. In the October 2026 case HPC staff
  confirmed the cause: the idle cores and memory were on nodes being held for
  **higher-priority parallel (multi-node) jobs**. Nothing was faulty. Single-core
  jobs wait behind promised multi-node allocations because the scheduler will not
  fragment a node it has committed. Shortening wall limits does not release such
  jobs; it only helps short diagnostics backfill onto genuinely free nodes.
- **`squeue --start` estimates are pessimistic and they move.** Staff noted that
  parallel jobs often finish before their requested wall clock, so real starts
  come earlier, while newly submitted work pushes them later. One ticket moved 22
  of 25 jobs about four days earlier than first projected. Do not plan a deadline
  on a projected start without saying it is a projection.
- **Priority is visible in `squeue -o "%Q"` and explains split behaviour.** When
  some jobs have a node assigned and others show `(null)` with a later date, the
  ones with no node are in a lower priority band and are not yet matched to
  hardware. Jobs in the same band generally start together.
- Login banner: Hazel prints planned-maintenance/status messages at every
  interactive login — actually read it rather than skipping past, especially
  before filing a ticket.

**None of these public pages give GPFS-specific latency/load metrics** — they
show network/interconnect and job-queue saturation, not filesystem I/O
health directly. So elevated utilization is suggestive, not proof, of a
filesystem-contention explanation.

**Escalating to HPC staff: Roland sends the email, never you.** The address
is `help@ncsu.edu`, which generates a ServiceNow ticket for HPC staff. Your job
is to draft the message and hand it to him as plain text he can paste into his
own mail client. He has stated this as a standing rule: Claude and Claude Code
never send email on his behalf, and he does not want to be asked again. Never
write an instruction to another agent telling it to send a message, and never
write "send the email" when you mean "draft it for Roland".

When reporting an unexplained slowdown, lead with
what you've already ruled out (unmodified script, same env by package
timestamp, same NIMBLE/R version, same node hardware generation, job's own
CPU efficiency near 100%) and ask an open question about what changed
cluster-side, rather than asserting a specific cause you can't verify from
inside a job — HPC staff have GPFS/network instrumentation you don't, and a
factual report gets a more useful answer than a leading guess.

## Relaying between the user and an agent working on Hazel

Work on Hazel usually runs through a second agent (Claude Code) with its own
session there, and the user is the only channel between the two: they paste its
reports in and paste prompts back. **Their attention is the scarce resource in
that loop, and Roland has said so twice** -- "I don't want trivial conversations
between you two to take up my time", and later, of a message that was mostly
confirmations, "don't waste my time".

So a Hazel report is not something to respond to. It is something to **screen**,
and most of it should stop with you.

### The test: surface it only if it is one of these

1. **It blocks.** A gate needs a human decision and work is stopped until it
   comes -- a flagged bundle the runner refuses to start, an approval, a
   launch/hold call, an expired session needing re-auth.
2. **It changes a reported number, or a decision already made.** A result moved,
   a count came back different from what a report or a previous message stated,
   or new evidence overturns something you told him.
3. **It is a disagreement needing him to adjudicate**, or a genuine scientific
   choice with a real trade-off -- not a mechanical one you can make yourself.
4. **It is an error you made** that he has acted on or would act on.

If none apply, do not send it. A one-line "nothing needs you, X is running" is
the whole response, and is often the right one.

### What to stop

Validation that passed. Confirmations that two things agree. Agreement with a
recommendation you already gave. Housekeeping (commits to push, files to move).
Terminology distinctions that matter only to the two agents. Process notes about
how something was checked. Numbers that merely confirm an earlier estimate. All
of it is real work and none of it needs him.

Batch anything worth keeping into the next message that *does* have a blocking
item, or into the write-up when results land.

### Writing the prompt back

Only draft a paste-ready prompt when it carries a **decision or a changed
instruction**. Don't draft one to acknowledge good work, confirm a plan already
agreed, or pass along a distinction the other agent will handle correctly
anyway. When a prompt is warranted, put the blocking item first -- the user may
send only the first paragraph.

If you are unsure whether something clears the bar, say plainly which single
item does and label the rest as skippable, rather than sending it all and
letting him sort it.

## When driving Hazel over SSH for the user

If a terminal session to Hazel is available, remember: every command runs on
a shared login node. Run `hostname` first to confirm where you are. Only
lightweight commands (file management, module loads, conda installs, sbatch,
squeue) belong there; anything compute-heavy gets wrapped in a batch script
instead of run directly. Prefer non-interactive forms (`sbatch`, `squeue`,
`sacct`) over `salloc`, since interactive allocations can hang a scripted
session while waiting for dispatch. Never run `conda init` repeatedly, and
never store data in `/usr/local/usrapps`.
