---
name: kays-analysis-report-standards
description: "How Roland Kays wants analysis results explained back to him: every report, memo, methods write-up, results summary, or chat answer describing an analysis must be self-explanatory to a working ecologist who is not a statistician. Use whenever delivering results, writing a methods or results document, summarizing what an analysis found, or reporting numbers from a model fit, simulation, or method comparison. Covers defining invented and technical terms before use, giving every number its units and its practical meaning, explaining each method in full rather than naming it, showing a figure for every substantive claim, using field-standard names instead of internal shorthand, and a pre-delivery self-check. Complements kays-document-format (deliver as .docx) and kays-scientific-writing-style (manuscript voice)."
metadata:
  authored_via: "claude-science"
  published_by: "agent"
  published_at: "2026-09-30T18:07:03.724Z"
  authored_by: "agent"
  authored_at: "2026-09-12T21:36:32.691Z"
  authoring_session: "e8ae01ce-d9c1-4c48-9d91-22908a03cf70"
  last_modified_by: "agent"
  last_modified_at: "2026-09-30T18:07:03.721Z"
---

# Explaining analysis results to Roland

Roland is a field ecologist and camera-trap methodologist. He reads statistics
fluently as a user, and he is not a statistician. He has said, repeatedly, that
reports come back too compressed and too full of jargon to use, and that being
told a result is not the same as being shown it.

The failure mode is always the same: the analysis is fine, and the write-up is
a set of conclusions with the reasoning and the units stripped out. Assume the
reader has not seen the analysis, cannot ask a follow-up question, and will not
look up a term.

## The eight rules

**1. Define every term before its first use, and define the ones we invented
most carefully of all.** A term coined during the project is unknown to
everyone, including Roland a month later. Give it a one-sentence definition, a
concrete example from the data, and where useful a contrast with its opposite.
If a term has a standard name in the literature, give that too. This applies
to coined project vocabulary (activity incidence, activity intensity, group
passage time, quilted plot model) and to imported technical vocabulary
(bandwidth, kernel, branching ratio, misassignment rate, censoring, excess
error, resultant length, plug-in rule).

**2. Every number carries its units, its scale, and its consequence.** A bare
decimal is unreadable. For each reported number say what it measures, what
units or scale it is on, what a big or small value would be, and what it means
in practice. "Excess error 0.0087" is a failure. "Choosing the interval this
way costs 0.0087 in the estimated proportion of the day a species is active --
that is, it lands within about one percentage point of the best threshold
available, where the proportion itself runs from 0 to 1 and a typical species
sits near 0.45" is the standard.

**3. Explain each method in full; never just name it.** Naming a method is not
describing it. Each one gets: what question it answers, what it assumes, what
it actually computes step by step, what it returns, how to read that output,
and where it fails. A reader should be able to decide whether they believe the
method without leaving the document. If a report compares N methods, all N get
this treatment, and the reader should be able to see why the ranking came out
as it did.

**4. Show it, do not assert it.** Every substantive claim that could be a
figure should be one. Each figure needs axis labels a stranger can read, a
caption saying what is plotted and how it was computed, and one sentence
stating the take-home in plain language. A results section that says a pattern
holds, without the panel that shows it, is not finished. Figures are the
deliverable; the prose is navigation between them.

**5. Use the field's names, not ours.** Internal shorthand reads as either
wrong or parochial. A one-minute independence interval is the Wildlife Insights
standard sequence interval, not a "lab convention." Prefer the name a reviewer
would recognize, and give the internal name in parentheses once if it is needed
to match a column or a file.

**6. Report the current state only — no changelog.** A report says what is
true now. It must not narrate how the analysis arrived there. These documents
get forwarded to collaborators who were not part of the working conversation,
and for them a history of superseded results is noise at best and confusing at
worst. Cut every instance of:

- "corrected from an earlier version", "we previously reported", "this
  retracts", "supersedes the earlier memo", "as we said before";
- sections framed as corrections, errata, or change logs;
- before-and-after comparisons of our own numbers, and any account of a bug we
  found in our own code.

If an earlier approach was wrong, the report simply contains the right one. A
genuine methodological finding that came out of fixing a mistake still belongs
in the document — but written as a property of the method, not as a story
about us: "the bandwidth rule checks three periodicities, and an implementation
that checks only the first fails on species whose peaks are twelve hours apart"
is current methods content; "we previously got this wrong" is not.

This does not license hiding anything. Limitations, caveats, and what was not
assessed are current facts about the work and stay in full. Version history, if
the user wants it, goes in the chat message or a separate file — never in the
document.

**7. A figure must be unable to mislead anyone who reads only the figure.**
Figures are the primary communication channel and they travel alone: they get
pasted into slides, forwarded, and skimmed without the surrounding prose. So a
figure carries the burden of being self-sufficient, and the load-bearing
qualifier goes in the TITLE, never only in the caption or a footnote. Small grey
explanatory text at the bottom of a panel is decoration, not a disclaimer --
assume it will not be read.

Concretely, for any figure depicting what the analysis *did* -- its spatial or
temporal scope, which data entered it, which model variant produced it, what was
included or excluded:

- **The title states what was actually run, not what the method intends.** "How
  the modelled area was defined" is a description of an approach. "Cells used by
  these fits, and what the union mask would add" is a statement about the run
  that produced the numbers beside it.
- **The title carries the number that proves it**, and that number is computed at
  render time from the same artifact the prose cites -- never hardcoded, never
  carried over from an earlier version of the figure. A panel title reading "588
  cells fitted | +257 in union" cannot drift out of step with the methods text;
  one reading "845 cells" can, and did.
- **Anything shown but not used is labelled as not used, in the legend entry
  itself.** A legend that reads "true absence cells" implies those cells are in
  the model. "IUCN range map only -- not in these fits" cannot be misread. If
  showing unused data would confuse more than it informs, leave it out.
- **When a claim in the prose is corrected, every figure asserting that claim is
  re-rendered in the same edit.** Correcting the text and leaving the figure is
  worse than leaving both wrong, because the document now contradicts itself and
  the reader believes the figure.

The concrete failure this rule exists to prevent: a methods figure titled "how
the modelled area was defined" displayed union-mask cell counts while the fits
had run on the presence mask. The methods text was corrected; the figure was not.
Each panel's count overstated the cells actually fitted -- bobcat 845 against 588
(+43.7%), white-tailed deer 750 against 655 (+14.5%), moose 183 against 178
(+2.8%) -- the caption asserted a rule the analysis had not followed, and nothing
in the prose could undo that for a reader who looked at the picture and moved on.
Note the error was largest for the species whose mask mattered least, so a
plausibility glance at any one panel would not have caught it.

**8. A results figure or table shows the current design only.** Superseded
variants belong in the memo, never in a deliverable. When a design decision is
settled, delete the comparison artifact rather than keeping it available.

The test: is every number on this figure one we would stand behind today? If
not, it does not belong on the figure at any weight, in any colour, however it
is labelled. "Superseded" in a legend does not make it safe -- a reader who
looks at the picture and moves on has now seen a number we disown.

This is separate from rule 7. Rule 7 is about a figure being unable to mislead
on its own; this one is about which results are eligible to appear at all. A
figure can be perfectly self-describing and still be reporting an abandoned
analysis.

What belongs in the memo instead: why the design changed, what the old one gave,
and what moved. Roland has said it twice -- of the simulation error-rate figure,
"the people we are writing for don't know our history, we just want to report
the results we have and not confuse them with details of our history that
aren't important for deciding what to do next"; and of a trend figure carrying
the superseded mask as a grey comparison series, "this added complexity only
adds confusion."

The pull to include the comparison comes from wanting to show *why* the design
changed. That is a methods argument for collaborators, not a result. Separate
the two: the deliverable reports what was found, the memo records how the
design got there.

## Structure that works

Lead with take-home points -- three to six numbered sentences, each one a
finding with its number and its practical consequence, readable on their own.
Then background and definitions, then methods in full, then results organized
around the figures, then what to do differently, then limitations in plain
terms. Put a short glossary at the front or the back of anything with more than
about five technical terms.

Prefer a table to a paragraph whenever more than three numbers are being
compared, and give the table a column saying what the number means.

## Limitations belong in the open

State what was cut, subsampled, or not verified, in the same plain language as
everything else, and say what it would take to close the gap. A caveat written
in jargon is a caveat that will be missed.

## Self-check before delivering

Read the draft as if handed it cold, and fix any of these:

- A term used before it is defined, or never defined.
- A number without units, scale, or a statement of what it implies.
- A method named but not described.
- A claim with no figure, where a figure was possible.
- **A figure whose title describes an intended method rather than the run that
  produced it**, or whose title lacks the number that proves what was used.
- **A figure number that was not recomputed from the artifact the prose cites**
  -- carried over from an earlier render, or typed in by hand.
- **A legend entry that implies data is in the model when it is not.**
- **A corrected claim whose figure was not re-rendered in the same edit.** Check
  every figure that touches the claim, not only the one you were looking at.
- **A superseded design, variant, or methods comparison appearing in a results
  figure or table at all** -- including as a greyed or explicitly-labelled
  comparison series.
- Internal shorthand where a field-standard name exists.
- A sentence you could not read aloud to a graduate student without stopping
  to explain a word.
- Any reference to a previous version, an earlier result, or a mistake we
  corrected — a collaborator reading this cold has no earlier version.

Length is not the problem and compression is not a virtue here. A long
document that can be read once and used beats a short one that has to be
interrogated.
