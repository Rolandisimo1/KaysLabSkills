# Kays Lab skills

Claude skills for the Kays Lab (NC State University / NC Museum of Natural
Sciences), packaged as a Claude plugin marketplace. Each plugin is a group of
related skills; install only the groups you use.

## Plugins

| Plugin | Skills | Audience |
|---|---|---|
| `research-workflow` | science-workflow-development | everyone writing analysis code |
| `camera-traps` | camera-trap-qc, camera-trap-activity-analysis, camtrap-interaction-analysis, wildlife-cv-pipeline | lab |
| `movement` | gps-tracking-analysis, biologging-acc-imu | lab |
| `modeling` | hierarchical-ecological-models, sdm-paper-verification | lab |
| `data-and-compute` | mdd-taxonomy, earth-engine, geocode-news, hazel-hpc | lab |
| `kays-writing` | kays-voice-core, kays-grant-writing-style, kays-scientific-writing-style, kays-popular-writing, kays-analysis-report-standards, kays-manuscript-revision-tracking | Roland, and anyone drafting text for him |
| `kays-personal` | wildlife-pop-env | Roland only (Claude Science) |
| `kays-projects` | camera-inat-stream-agreement, diel-activity-conventions | Roland only; each should move into its project's repo |

## Install

**Claude Code** (needs read access to this repo and stored git credentials:
`gh auth login`, then `gh auth setup-git`):

```
/plugin marketplace add Rolandisimo1/KaysLabSkills
/plugin install research-workflow@kays-lab-skills
/plugin install camera-traps@kays-lab-skills
```

Turn on auto-update for the marketplace in `/plugin` > Marketplaces, or run
`/plugin marketplace update kays-lab-skills` to pull changes.

**Claude app**: Customize > Skills > upload a single skill folder as a zip, or
Customize > Plugins > Add from a repository.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: work on a branch, open a pull
request, and Roland merges.

## Provenance

The tag `baseline-2026-10-11` holds every skill exactly as it was imported from
Roland's Claude account. `git diff baseline-2026-10-11` shows all changes since.
