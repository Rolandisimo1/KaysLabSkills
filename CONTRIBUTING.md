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

## Where a skill goes

- Useful to anyone in the lab: one of the lab plugins.
- One project only: that project's own repo, in `.claude/skills/`.
- One person's preferences: that person's own account, or a personal plugin.

## Test triggering after a change

`tests/check-triggers.sh` runs each prompt in `tests/trigger_prompts.tsv`
through Claude Code and reports which skills loaded, against
`tests/expected.tsv`. Add a prompt and its expected skills whenever you add a
skill. Runs vary, so use at least two runs per prompt.
