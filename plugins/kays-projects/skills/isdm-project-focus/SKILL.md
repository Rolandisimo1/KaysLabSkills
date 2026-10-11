---
name: isdm-project-focus
description: "PRIMARY OBJECTIVE for the camera-trap + iNaturalist abundance project: deliver continental population trends for the 34-species fleet, camera-anchored, as a report for Krishna and Arielle. Everything else -- range masks, urban-rural screens, estimator comparisons, convergence forensics -- is method QC serving that table. Load at the start of any work session on this project, and re-read before responding to an incoming cluster report."
metadata:
  authored_via: "claude-science"
  published_by: "agent"
  published_at: "2026-10-06T01:01:04.019Z"
  authored_by: "agent"
  authored_at: "2026-10-06T01:01:04.016Z"
  authoring_session: "183aba19-810a-4a8c-beef-ca2c06d952db"
  last_modified_by: "agent"
  last_modified_at: "2026-10-06T01:01:04.016Z"
---

# Primary objective

**Continental population trends for the mammal fleet, estimated jointly from
camera traps and iNaturalist, delivered as a report to Krishna and Arielle.**

The unit of progress is **species with a reportable trend**. Nothing else is
progress. A method check that returns in nine minutes is not progress; a chain
that finishes and is never extracted is not progress either.

## The standing rule

**Open every response to an incoming cluster report with where the trend table
stands** -- species extracted, species fitted-but-unextracted, what is blocking.
One or two lines. Then handle whatever the report actually contained.

If a turn's work was QC, say so in those words and say what it changed about
the trend table. If it changed nothing about the trend table, that is the
honest headline, and the QC output is a supporting detail rather than the
answer.

**Never lead a response with a QC figure.** A reader opening the reply should
see the state of the deliverable first. A figure answering a question the user
did not ask, with its framing below it, is a reporting failure even when the
figure is correct.

## What counts as a side-quest here

All of these are real and some have changed the numbers materially. None of
them is the objective:

- range-mask construction and comparison (presence / IUCN / union)
- the urban-rural stream screen and the `year_pop` model extension
- estimator comparisons (occupancy vs Royle-Nichols, array vs camera level)
- convergence forensics, chunking defects, scheduler and memory tuning
- covariate collinearity and taxonomy crosswalks

Handle each in a **bounded** way: answer it, record the finding where it
belongs (skill, memo, or `STATUS.md`), and return to the trend table in the
same response. A side-quest that spawns a second side-quest without the trend
table having moved is the failure mode this file exists to prevent.

## The check before dispatching work to the cluster

Before writing any prompt for the cluster agent, ask: **does this get a species
from fitted to reportable?** If not, it goes behind whatever does. Chains that
have finished and sit unextracted are the most common form of silent
stall -- cluster traffic reports them as "complete", which reads like progress
and is not.

## Where the live state lives

`prototype_spatial_trend/STATUS.md` -- the current trend-table state, the
blocker, and the parked side-quests. Read it when resuming after a gap; update
it whenever a species moves from fitted to reportable, or a side-quest opens or
closes. It is the memory that survives context folding, daemon restarts and
multi-week gaps; do not rely on recalling project state from conversation.

## Reporting conventions

Writing results up is governed by `kays-analysis-report-standards`; stream
interpretation and the camera/iNaturalist agreement rule by
`camera-inat-stream-agreement`. This file governs only what gets worked on and
what leads a response.
