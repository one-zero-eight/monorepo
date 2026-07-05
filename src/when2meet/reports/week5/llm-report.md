# LLM Usage Report

## Summary

During Week 5 (Assignment 5 / Sprint 3) we used AI/LLM tools for:

1. **Speech-to-text** via [speech2text.ru](https://speech2text.ru/) to produce the raw recording transcript of the Sprint Review and customer UAT session.
2. **Translation** from Russian to English for [sprint-review-transcript.md](sprint-review-transcript.md) and drafting support for [sprint-review-summary.md](sprint-review-summary.md).
3. **GitHub Copilot Autofix powered by AI** on selected pull requests — suggestions reviewed before merge.
4. **Cursor (Composer)** for drafting Week 5 report structure, MkDocs setup, and architecture doc corrections — human-reviewed before merge.

No LLM was used for defining quality requirement scenarios, writing pytest/QRT assertions without review, making merge decisions without review, or inventing customer UAT outcomes.

## Tools

| Tool | Purpose |
| --- | --- |
| [speech2text.ru](https://speech2text.ru/) | Transcribe Sprint Review + UAT recording |
| LLM translation (vendor not fixed) | English transcript and summary drafting |
| GitHub Copilot Autofix powered by AI | Suggest code fixes on PRs |
| Cursor (Composer) | Report/docs scaffolding and React architecture correction |

## What was produced without LLM assistance

- MVP v2 React frontend increment and backend slot-preservation policy ([#106](https://github.com/one-zero-eight/monorepo/pull/106))
- QR-004 / QRT-004 ([#108](https://github.com/one-zero-eight/monorepo/pull/108))
- PlantUML sources reviewed against the codebase; diagrams regenerated with local PlantUML
- Public demo video recording ([Yandex Disk](https://disk.yandex.ru/i/HMPVXl3bnmYL0g))
- CI workflows, secret scan, and deployment to `pre.innohassle.ru/when2meet`

## Review

Transcript and summary were checked against the recording before publication. Copilot and Cursor drafts were reviewed in PRs or pair review before merge. Private recording links and identifying customer details stay in the Moodle PDF only.
