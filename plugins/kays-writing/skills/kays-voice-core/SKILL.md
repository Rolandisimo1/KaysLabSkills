---
name: kays-voice-core
description: "Roland Kays's writing voice, required for any text written as or for Roland, however short: tightening or rewording a sentence or paragraph, editing a draft, writing an email, letter, or message, and drafting manuscripts, abstracts, grants, reviews, reviewer responses, reports, memos, blog posts, or talk scripts. Covers the banned rhetorical patterns (hedged negation, abstraction as agent, contrastive negation like 'rather than' or 'not merely', self-grading sentences), em dashes, spelling, stating limitations and rigor, length limits, .docx delivery, and a scan to run before handing over any text. Load alongside the scientific, grant, or popular writing skill for longer pieces."
---

# Kays voice: rules for every register

These rules apply to everything Roland writes or reads from you. The register
skills (scientific, grant, popular) add structure and tone on top. Where a
register skill and this file disagree, the register skill wins for that
register only; this file notes the known exceptions.

## Sentence-level rules

1. **Concrete subject, active verb.** "We fitted the model," not "The model
   was fitted." Use "we" in papers and grants, "I" in popular and personal
   writing. Passive voice only where the actor does not matter.
2. **State facts and let the reader judge.** Do not write sentences that grade
   the writing's own design, argument, or evidence. Cut "this lets us
   decompose the pathway instead of assuming it" and "this approach is
   robust"; write what was done and what it showed.
3. **No contrastive-negation framing.** Phrases like "rather than," "not
   merely," and "this is by design, not a limitation" name the criticism
   being pre-empted and make it more salient. State the positive claim alone.
4. **Supply the evidence for rigor.** Where a sentence wants to say an
   analysis is careful, rigorous, or validated, replace the adjective with the
   specific measurement, comparison, or control: the simulation, the holdout,
   the sample size, the recovered parameter.
5. **Limitations in one plain sentence.** State the limitation and, if useful,
   what would close it. Do not argue that it is not really a limitation.
6. **Em dashes: avoid.** Use a comma, colon, parentheses, or two sentences.
   Popular register exception: spaced hyphens for conversational asides.
7. **Hit the requested length.** Roland's drafts and Claude's drafts both
   tend to run long. When a length is given, meet it; when none is given,
   cut anything that restates.
8. **Spelling and conventions.** American spelling unless the target journal
   requires British. Match the journal's citation and abstract format.

## The hedged-negation / abstraction-as-agent voice

A recurring failure mode that reads as machine-written even when it passes
every vocabulary check. It is a small set of rhetorical substitutions for a
direct, declarative statement. Scan every draft for these eight patterns.

**1. Negative-assertion framing.** Making a claim by stating what was not done
or not found.
- Avoid: "I do not report a single number for how much of the variation is
  regional rather than local."
- Prefer: state what the data support, and why a single number is not
  meaningful, as its own plain sentence.
- Avoid: "I do not claim that a shift of that size carries a measurable cost
  to the animal."
- Prefer: "Whether a shift of this size carries a measurable cost to the
  animal is untested here." Or cut the sentence if it is only a disclaimer.

**2. Abstraction as agent.** An abstract noun (a baseline, a correction, an
effect) as the subject acting on another abstraction (meaning,
interpretation, weight).
- Avoid: "A continental baseline changes what a future observation can mean."
- Prefer: "Future surveys now have this baseline to compare against."
- Avoid: "[Effects] are the ones that carry real interpretive weight."
- Prefer: name what the effects show or why they matter more than the others.

**3. The "reading rather than merely X" scaffold.**
- Avoid: "...has a biological reading rather than a merely technical one."
- Prefer: "...is a biological result, not a technical artifact."

**4. Procedural or financial metaphors for method choices** ("bookkeeping,"
"housekeeping").
- Avoid: "A measurement-error correction is not optional bookkeeping."
- Prefer: "A measurement-error correction is necessary here: skipping it
  [state the concrete consequence]."

**5. Emphasis by do-support** with no contrast in play.
- Avoid: "Environmental conditions do move activity."
- Prefer: "Environmental conditions move activity." Keep "do move" for a real
  contrast: "...move activity despite the weak correlation."

**6. Restating a claim by its negation.**
- Avoid: "Human density moves species in opposite directions ... they do not
  move together."
- Prefer: keep the first sentence; cut the second or replace it with a new fact.

**7. Embedded meta-hedging**, a claim's epistemic status tucked into the same
sentence.
- Avoid: "I assigned this grouping after seeing the pattern, so I present it
  as an explanation to be tested rather than a confirmed result."
- Prefer two sentences: state the grouping. Then: "This grouping was chosen
  after seeing the pattern and should be tested in new data."

**8. Fragment as pivot in technical prose.** A clipped sentence ("My exposure
also differs.") opening a paragraph for drama. Expand it into a full sentence
with its own content. Popular register exception: a one-sentence pivot
paragraph is a deliberate tool there, provided it is a real sentence with
content ("Then the bison didn't go extinct").

None of these constructions is wrong in isolation. The failure is using one
in place of a plain sentence with a concrete subject and an active verb. When
a sentence's subject is an abstraction and its verb is mental action (means,
shows, argues, suggests, carries weight), or when it states what was not done
instead of what was, rewrite it plain.

## Delivery format

Prose deliverables (manuscripts, sections, reviews, reports, memos, methods
write-ups, reviewer responses) go to Roland as Word `.docx`, not markdown.
Data stay in native formats (`.csv`, `.png`/`.pdf`, `.R`/`.py`). See
`references/docx-delivery.md` for pandoc conversion, figure embedding, DOI
hyperlinks, and checks on the output file.

## Scan before handing over a draft

- Every sentence has a concrete subject; no abstraction is doing the acting.
- No sentence states what was not done in place of what was.
- No "rather than," "not merely," or self-grading sentence.
- Every claim of care or rigor is backed by a number or a named check.
- Limitations are one plain sentence each.
- No em dashes (popular register: spaced hyphens allowed).
- Length matches the request.
