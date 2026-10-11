---
name: kays-manuscript-revision-tracking
description: "How to handle Roland Kays's manuscript and figure revisions: tracking outstanding requests across turns so none is dropped, working reviewer comments on a document before any other task, deciding figure details without asking, and verifying the artifact actually shipped. Use whenever the user sends comments on a manuscript, results outline, methods section or figure, or whenever more than one request is open at once."
metadata:
  authored_via: "claude-science"
  published_by: "agent"
  published_at: "2026-09-20T20:38:24.278Z"
  authored_by: "agent"
  authored_at: "2026-09-20T20:36:52.024Z"
  authoring_session: "e8ae01ce-d9c1-4c48-9d91-22908a03cf70"
  last_modified_by: "agent"
  last_modified_at: "2026-09-20T20:37:54.904Z"
---

# Handling manuscript revisions without dropping requests

Roland works on several threads at once and will send a new request before the
previous one is finished. That is normal and it is not his job to slow down.
Keeping the open items straight is the assistant's job. This skill exists
because it was not done: comments on a figure were listed in a reply and then
left undone for two further turns, twice.

## The ledger

Keep an explicit list of open items. Restate it at the END of every reply,
marked by owner:

```
Outstanding:
1. <item>  - mine
2. <item>  - waiting on you: <exactly what is needed>
```

Rules for the ledger:

- An item leaves the list only when the artifact is saved and verified, not
  when it is planned or described.
- An item **blocked on the user** stays on the list every turn until answered.
  Do not silently drop it because it was mentioned once.
- If a reply cannot address every open item, say which were not touched. A
  reply that reports progress on new work while an older commitment is
  untouched reads as the older one having been forgotten.
- Never write "I'll do X next" and then open the next turn with something
  else. If priorities changed, say so explicitly.

## Document comments come first

When a `.docx` arrives with tracked comments, extract and work **all** of them
before any other task in that turn, including reviewer findings, follow-up
analysis, or anything more interesting. Comments are the reason the file was
sent.

Extract them with the comment ranges so each is paired with its anchor text:

```python
z = zipfile.ZipFile(host.artifact_path(version_id))
doc = z.read("word/document.xml").decode("utf-8", "replace")
cx  = z.read("word/comments.xml").decode("utf-8", "replace")
```

Then list every comment with its anchor before starting, and confirm each one
individually in the reply. Listing them and not doing them is worse than
missing them, because it proves they were read.

## Do not ask about figure details

Questions like "should this be a new panel or its own figure?" stall the work
for a full round trip and are easy to mistake for progress. Build a version,
show it, and let him redirect. He does, quickly, and the redirect is cheaper
than the question.

Reserve questions for things that cannot be guessed and cannot be reversed:
which citation covers a survey year, whether data may be shared before
publication, which of two scientific interpretations to adopt.

## Verify the artifact you are shipping

Check the file that is being delivered, not a file derived from it. A `.docx`
compiled from a substituted copy can be correct while the saved source still
contains placeholders. Read the saved artifact back and assert on its contents:

```python
d = Document(host.artifact_path(saved_version_id))
assert len([x for x in d.part.rels.values() if "image" in x.reltype]) == n_expected
```

## Never write a method that was not performed

If a comment asks "why not do it in R?", either run it in R or state honestly
why not. Editing the sentence to claim the R package was used, without calling
it, puts an unverifiable false claim into a Methods section. This happened once
in this project and was caught only by review.

Before writing any sentence describing what was done, confirm a tool call in
the session actually did it.
