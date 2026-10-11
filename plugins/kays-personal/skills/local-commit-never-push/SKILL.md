---
name: local-commit-never-push
description: Roland's git workflow for research code — agents write files to his hard drive and commit locally, but NEVER push to a remote. He pushes manually so he knows when and why code becomes public. Use whenever committing, versioning, or being asked to "put this on GitHub" for any project in this workspace, and when instructing Claude Code or another agent to do git work on his behalf.
---

# Local commit, never push

Roland's standing rule for every repository in this workspace:

**Agents write to his hard drive and commit locally. Agents never push.**

He pushes manually. The reason is control over timing and intent: a push is
the moment code becomes visible to collaborators or the public, and he wants
to be the one who decides when that happens and to know why. This is not a
credentials problem to work around — it is the workflow.

## What to do

- Write files to the project directory on his drive.
- `git add` / `git commit` freely, with real commit messages.
- **Stop there.** Report what was committed and that it is ready for him to
  push.
- Never run `git push`, `gh repo create`, `gh pr create`, or any command that
  publishes. Never configure a credential helper to enable one.

## When instructing another agent (e.g. Claude Code)

State the rule explicitly in the prompt rather than assuming it. Phrase it as
policy, not circumstance:

> Commit locally to Roland's drive. Do not push — he pushes manually so he
> knows when and why. Report what you committed and stop.

An agent that stops only because credentials happen to be missing has done
the right thing for the wrong reason, and will push as soon as credentials
exist. Say the rule.

## Repository visibility

Before recommending that anything be committed toward a remote, check whether
that remote is public or private, and tell him what you find — do not assume
a repo is private because it was intended to be. A public research repo may
be fine, but it is his call to make knowingly. He fixes visibility himself in
the GitHub web UI.

## Commit hygiene that matters to him

- **Never write a commit message, README, or code comment that claims code is
  validated or tested when it isn't.** Mark unvalidated work UNVALIDATED and
  keep it that way until a test has actually passed. Overclaiming in a commit
  message has cost this project real time.
- **Establish a fork point for inherited code.** When a project builds on
  code received from someone else, commit their files exactly as received as
  a baseline (an orphan branch plus a tag works well on a repo whose history
  already diverged), so `git diff` against it becomes the provenance record
  instead of something reconstructed by hand later.
- **Watch for `.gitattributes` normalizing line endings** when byte-exactness
  matters for a provenance baseline — `* text=auto` will silently rewrite
  CRLF to LF. Commit such files with `--no-filters` and pin `* -text`, then
  verify checksums against the source archive.
