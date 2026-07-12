# LLM Usage Report

## Summary

During Week 6 (Assignment 6 / Sprint 4) the team used AI/LLM tools for:

1. **Speech-to-text** via [speech2text.ru](https://speech2text.ru/) to produce the raw recording transcript of the Sprint Review / transition / UAT session.
2. **Translation** from Russian to English for [sprint-review-transcript.md](sprint-review-transcript.md) and drafting support for [sprint-review-summary.md](sprint-review-summary.md).
3. **GitHub Copilot Autofix powered by AI** on selected pull requests — suggestions reviewed before merge.
4. **Cursor (Composer)** for scaffolding Week 6 report structure and Moodle PDF Typst sources — human-reviewed before merge.

No LLM was used for inventing customer UAT outcomes, inventing documentation-review results, making merge decisions without review, or writing unreviewed pytest/QRT assertions.

## Tools

| Tool | Purpose |
| --- | --- |
| [speech2text.ru](https://speech2text.ru/) | Transcribe Sprint Review + transition + UAT recording |
| LLM translation (vendor not fixed) | English transcript and summary drafting |
| GitHub Copilot Autofix powered by AI | Suggest code fixes on PRs |
| Cursor (Composer) | Week 6 report / PDF scaffolding |

## What was produced without LLM assistance

- Selected meeting-time and room-booking backend/frontend increments ([#136](https://github.com/one-zero-eight/monorepo/pull/136)–[#139](https://github.com/one-zero-eight/monorepo/pull/139))
- Customer handover and README updates ([#133](https://github.com/one-zero-eight/monorepo/pull/133), [#147](https://github.com/one-zero-eight/monorepo/pull/147), [#148](https://github.com/one-zero-eight/monorepo/pull/148))
- Sprint Review recording, customer documentation review, and UAT execution with the customer
- Rehearsed presentation deck and standing presentation rehearsal
- CI, secret scan, and deployment verification on `pre.innohassle.ru/when2meet`

## Review

Transcript and summary were checked against the recording before publication. Copilot and Cursor drafts were reviewed in PRs or pair review before merge. Private recording links, credentials, and identifying customer details stay in the Moodle PDF only.
