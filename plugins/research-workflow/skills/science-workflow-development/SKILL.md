---
name: science-workflow-development
description: "Lab rules for developing research analysis code, including saving and pushing it: when to commit, when and where to push to GitHub, what never to commit (data, credentials), keeping the project focused on its main deliverable with side-quests bounded, and keeping every figure, table, and result in committed pipeline code that regenerates it. Use when saving code, committing, pushing to GitHub, or putting code online; starting, resuming, or planning an analysis project; deciding what to work on next; writing analysis code in R or Python; producing figures or results that will be regenerated; dispatching cluster jobs; or when a session drifts into QC, debugging, or method comparisons."
---

# Science workflow development

Three disciplines for any session that writes analysis code:

1. **Focus.** Know the deliverable and report against it.
2. **Pipeline.** Everything that produces a result lives in committed code.
3. **Save and push.** Commit at milestones and push to GitHub regularly.

## 1. Focus on the deliverable

Every analysis project has one primary objective, stated as a deliverable:
"continental population trends for 34 species, as a report for the
co-authors," not "work on the trend model." The unit of progress is a piece of
that deliverable moving to done (a species with a reportable trend, a figure
in final form). A diagnostic that ran is not progress. A model that finished
and was never extracted is not progress.

**`STATUS.md` at the repository root** holds the objective, the unit of
progress, where the deliverable stands, the current blocker, and the parked
side-quests. Read it at the start of every session and after any gap. Update
it whenever a unit moves to done or a side-quest opens or closes. It is the
memory that survives long gaps and context resets; do not rely on recalling
project state from conversation. If a project has no `STATUS.md`, write one
with the user before writing code. Template: `references/status-template.md`.

**Open every progress report with where the deliverable stands**, in one or
two lines (done, in progress, blocked by what). Then cover whatever the turn
was about. If the turn's work was QC or debugging, say so and say what it
changed about the deliverable; if it changed nothing, that is the headline.
Never lead a reply with a QC figure.

**Side-quests are bounded.** Range-mask comparisons, estimator comparisons,
convergence forensics, scheduler and memory tuning, taxonomy crosswalks: all
real, sometimes important, none the objective. Handle each by answering it,
recording the finding (in `STATUS.md`, a skill, or a memo), and returning to
the deliverable in the same reply. A side-quest that opens a second
side-quest before the deliverable has moved is the failure this section
exists to prevent.

**Before dispatching a long job** (cluster run, another agent, a large
download), ask whether it moves a unit toward done. If not, it waits behind
whatever does. Finished-but-unextracted results are the most common silent
stall: a job reported as "complete" reads like progress and is not until its
output is in the results table.

## 2. Pipeline over session

If a result will ever be produced twice, it belongs in committed code.
Figures, report builders, tables, QC screens, prediction surfaces: each is a
function in a module in the repository. A session calls the pipeline and
reviews the output; it does not reimplement it.

    repo/
      STATUS.md     objective, state, blocker, parked side-quests
      lib/          reusable primitives
      pipeline/     analysis stages, numbered in run order
      figures/      one function per figure, plus a runner
      reports/      document builders
      methods/      methods text as submitted

Four requirements:

1. **Inputs resolve by name or documented path**, never by a file that
   happened to be in someone's workspace. Test by running from a clean
   checkout.
2. **Conventions learned the hard way become assertions** next to the code
   that depends on them, so a wrong figure fails loudly.
3. **Choices live in named constants with the reason** (palettes,
   thresholds, guild boundaries), so the next session does not re-litigate them.
4. **One command regenerates every figure and result** from the inputs.
   Keep that command in the README and run it before any result goes to a
   co-author.

A session is for calling the pipeline, reading the output, deciding what to
change, changing the module, and rerunning. One-off exploration stays in the
session. After regenerating a figure, look at it: no overlapping text, nothing
crossing a panel border, numbers matching the artifact they came from.

Details, the failure that motivated the rule, and how to recover a figure
whose code was never committed: `references/pipeline-over-session.md`.

## 3. Save and push

**Commit at each milestone**: a working function, a new or changed figure, a
change to a results table, the end of a session. Write real commit messages
that say what changed and why.

**Push to GitHub at least at the end of every working session**, and after
any milestone a collaborator is waiting for. Code that exists only on one
laptop or in one session is lost.

- **Solo project repository:** push to `main`.
- **Shared repository** (the lab skills repo, co-authored analysis code):
  push a branch and open a pull request; the repository owner merges.
- **Before the first push to any remote, check whether it is public or
  private and tell the user.** Do not assume a repository is private because
  it was intended to be.

Never, without the user's explicit instruction in that conversation:
- create a repository, or change a repository's visibility;
- force-push, or rewrite history that has already been pushed;
- commit raw data, unpublished data the user is not cleared to share,
  credentials, API keys, `.env` files, or files over 50 MB. Keep a
  `.gitignore` that excludes data directories and secrets.

When instructing another agent (Claude Code on a cluster, for example), state
these rules in the prompt; do not assume it knows them.

**Commit hygiene:**
- Never write a commit message, README, or comment claiming code is
  validated or tested when it is not. Mark such work UNVALIDATED until a test
  has passed.
- Never describe a method in text that the code did not run. Confirm a tool
  call actually did it before writing the sentence.
- **Fork point for inherited code.** When building on code received from
  someone else, commit their files exactly as received as a tagged baseline
  first, so `git diff` against it is the provenance record.
- `.gitattributes` with `* text=auto` rewrites line endings. When a
  provenance baseline must be byte-exact, commit it with `--no-filters`, pin
  `* -text` for those files, and verify checksums against the source.

## Related skills

- Writing up results: `kays-analysis-report-standards`.
- Running jobs on the NCSU cluster: `hazel-hpc`.
