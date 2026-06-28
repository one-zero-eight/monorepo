# LLM Usage Report

## Summary

During Week 4 (Assignment 4 / Sprint 2) we used AI/LLM tools for:

1. **Speech-to-text** via [speech2text.ru](https://speech2text.ru/) to produce the raw Russian transcript of the Sprint Review and customer UAT recording.
2. **Translation** of transcribed meeting content from Russian into English for internal drafting of the customer review summary (public version is sanitized separately).
3. **GitHub Copilot Autofix powered by AI** on selected pull requests — automated fix suggestions that the team reviewed and accepted or rejected before merge.

No LLM was used for defining quality requirements scenarios, writing pytest/QRT tests, configuring CI workflows, prioritizing the Product Backlog, or making merge decisions without human review.

## Tools

| Tool | Purpose |
| --- | --- |
| [speech2text.ru](https://speech2text.ru/) | Transcribe the Sprint Review + UAT recording |
| LLM translation (tool not fixed to a single vendor) | Draft English meeting notes from Russian transcription |
| GitHub Copilot Autofix powered by AI | Suggest code fixes on PRs; reviewed by team before merge |

## What was produced without LLM assistance

- Sprint implementation (frontend features, API integration, deployment to `pre.innohassle.ru/when2meet`)
- `docs/quality-requirements.md`, `docs/quality-requirement-tests.md`, and QRT pytest modules
- `docs/testing.md`, `docs/user-acceptance-tests.md`, and updates to `docs/definition-of-done.md`
- When2Meet pytest suite and CI configuration (tests workflow, secret scan workflow)
- Public demo video recording and presentation preparation
- Week 4 reflection, retrospective, and report index structure

## Review

English summary content was checked against the recording and team notes before publication. Copilot Autofix suggestions were reviewed in PRs before merge. Private recording links and identifying details are kept in the Moodle submission only.
