# STATUS.md template

Copy to the root of an analysis repository and fill in with the user.

```markdown
# <Project name>: status

## Primary objective
<The deliverable, its audience, and its form. Example: continental population
trends for the 34-species set, estimated jointly from camera traps and
iNaturalist, delivered as a report to the co-authors.>

## Unit of progress
<What counts as one step done. Example: a species with a reportable trend
(fitted, converged, extracted, passed the stream-agreement screen).>

## Where it stands (updated <date>)
- Done: <n of N units, list>
- In progress: <units, what stage>
- Blocked: <the single current blocker, and what would clear it>

## Regenerate everything
`<one command that rebuilds every figure and result from inputs>`

## Parked side-quests
- <question>: <why parked, finding so far, what would reopen it>

## Decisions already made
- <convention or choice>: <reason, date>
```

Rules for keeping it useful:
- Update "Where it stands" whenever a unit moves to done, not at the end of
  the week.
- A side-quest gets one line when it opens and its finding when it closes.
- Delete parked items that are resolved; this is the current state, not a log.
