# Pipeline over session: details

Reference for science-workflow-development (formerly the pipeline-over-session skill).

If a deliverable will ever be produced twice, it belongs in committed code.

## The failure this prevents

A figure is built in a session. It looks good. Months later it needs a colour
change, a new species, an updated number. The code lives in a kernel that is
long gone, so the next agent rebuilds it from the data: re-deriving the
projection, re-choosing the palette, re-discovering which axis convention the
time variable uses. The rebuild introduces errors the original did not have,
and the reviewer catches them if they are lucky.

Observed cost in one project: an hour spent reverse-engineering a map
projection whose parameters were stored in the file all along, and a
centrepiece figure drawn with the time axis shifted six hours because the
sun-time origin had to be rediscovered.

## The rule

**Every step that produces a deliverable is a function in a module in the
repository.** Figures, report builders, table generators, QC screens,
prediction surfaces. A session calls the pipeline and reviews the output. It
does not reimplement it.

Concretely:

    repo/
      lib/          reusable primitives
      pipeline/     analysis stages, in order
      figures/      one function per figure, plus a runner
      reports/      document builders
      methods/      the methods text as submitted

## Four requirements

### 1. Inputs resolve by name, not by hand-staged path

A module that needs a file looks it up by filename (in Claude Science, in the
artifact store), or takes a documented path parameter with a default. It never depends on a file
that happened to be in someone's workspace.

    INPUTS = {"sites": "site_analysis_table_v2.csv", ...}

    def load_all(host, extra=None):
        ...resolve each name, return a dict...

This is what makes the pipeline runnable from a clean checkout. Test it by
running from a fresh kernel with nothing staged.

### 2. Conventions that have caused a bug become assertions

When a convention is discovered the hard way, encode it next to the code that
depends on it, as a check that fails loudly rather than a comment that is not
read.

    def verify_curve_convention(harmonics, tol=1.0):
        """Night share recomputed from the curves must match the stored measure.

        Exists because drawing sun-anchored time as midnight-to-midnight
        silently puts nocturnal species in daylight.
        """
        ...
        if worst > tol:
            raise AssertionError("sun-time convention wrong: ...")

Then every figure that draws curves calls it. The check is cheap; the error it
catches is a figure that looks plausible and is wrong.

### 3. Choices live in named constants, with the reason

Palettes, thresholds, colormaps, guild boundaries. Put them at module top with
a comment saying why, so the next iteration does not re-litigate them.

    # Boundaries set by the PI: under 20 percent nocturnal is diurnal.
    GUILD_BOUNDS = (20.0, 80.0)
    GUILD_COLOUR = {"diurnal": "#D08C1F", ...}
    CYCLIC_CMAP = "twilight"    # for circular quantities ONLY

### 4. Commit before the session ends

Code that exists only in a workspace is lost. Write it to the repository,
commit, and push following the rules in SKILL.md section 3.

## What a session is for

Calling the pipeline, reading the output, deciding what to change, changing the
module, rerunning. Exploration and one-off diagnostics are fine in a session,
and they should stay there. The test is whether anyone will want the result
again.

## Recovering a lost figure

If a figure's code was never committed, do not redraw it from scratch. In
Claude Science, which records the code that produced each artifact, read it
out of the artifact's lineage first (this `host` object exists only there):

    lin = host.lineage[version_id]
    lin["code"]        # the cell that made it

Palettes, thresholds and layout choices are recoverable this way, and matching
the original exactly is usually the point. Then move that code into the module
so the next person does not repeat the recovery.

## Reviewing your own output

A figure regenerated from a pipeline still needs looking at. Read it back,
check that no text overlaps and nothing crosses a panel border, and confirm the
numbers on it against the artifact they came from. One corrective pass is
normally enough; do not iterate on styling.
