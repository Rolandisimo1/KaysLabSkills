# Adding or changing a skill

## Workflow

1. Create a branch: `git switch -c add-<skill-name>`.
2. Add or edit the skill under `plugins/<group>/skills/<skill-name>/`.
3. Run `claude plugin validate .` from the repo root.
4. Try the skill on a real task before opening the pull request.
5. Open a pull request saying what the skill does and what task you tested it on.

## What makes a skill trigger

Claude decides whether to load a skill from its `description` alone. The body
is read only after that decision.

- Start with what the skill does in one sentence, then a "Use when..." list of
  the tasks and words a person would actually type: package names, file types,
  data sources, document parts.
- 300 to 900 characters. The hard limit is 1024.
- Quote the description in double quotes. A colon followed by a space inside
  an unquoted description breaks the YAML header.
- Name the skill for its method or task (`gps-tracking-analysis`), not a
  person. Credit people in the body.

## What makes a skill useful

- One job per skill. If the description needs "and also", consider two skills.
- Keep SKILL.md under about 500 lines. Move long reference tables, code, and
  worked examples into `references/` or `scripts/` and say in SKILL.md when to
  read each file.
- Put deterministic steps in scripts (parsing, QC checks, validation) and keep
  judgment in the prose.
- Each rule should come with the failure it prevents, ideally with the real
  numbers from the time it went wrong. Those are what keep the next person
  from undoing it.
- Write the skill in the style you want the output to have. Claude copies the
  style of its instructions; a skill that bans em dashes should not use them.
- Do not put data, credentials, or unpublished results in a skill.
- Mark anything untested as UNVALIDATED in the skill and the commit message.

## Edits made inside Claude Code or Claude Science

A skill is used from two places besides this repo: Claude Code's account skills
and the Claude Science skill store. An edit made in one of those and not
mirrored here is invisible to the rest of the lab, and is reverted the next time
someone reinstalls the plugin. The repo is the canonical copy.

Mirror the edit into `plugins/<group>/skills/<skill-name>/` in the same working
session that made it, and diff rather than overwrite, since the repo copy may
carry someone else's change.

`scripts/skill-sync.sh` reports drift between this repo and both stores, and
copies a single named skill in either direction after showing the diff. It must
run natively, since the stores sit outside any sandbox, and it is UNVALIDATED.

## Where a skill goes

- Useful to anyone in the lab: one of the lab plugins.
- One project only: that project's own repo, in `.claude/skills/`.
- One person's preferences: that person's own account, or a personal plugin.

## Test triggering after a change

`tests/check-triggers.sh` runs each prompt in `tests/trigger_prompts.tsv`
through Claude Code and reports which skills loaded, against
`tests/expected.tsv`. Add a prompt and its expected skills whenever you add a
skill. Runs vary, so use at least two runs per prompt.

## Fewer skills trigger better

Measured on 2026-10-11 in Claude Code. With all eight plugins installed next
to Roland's 39 account skills (which included old copies of many of these),
the writing voice skill loaded for a one-sentence edit or a short email in 1 of 8
runs; with only the writing plugin installed, 8 of 8. With the account
duplicates turned off and the current descriptions, the edit, email, push,
and abstract prompts loaded their intended skills in 16 of 16 runs. Keep one
copy of each skill enabled, and turn off plugins you do not use.
