# LLM Usage Report

## Summary

During Week 7 (Assignment 6 / Sprint 5) the team used AI/LLM tools for:

1. **Speech-to-text** via [speech2text.ru](https://speech2text.ru/) to produce the raw recording transcript of the Sprint Review / final transition / UAT confirmation session.
2. **Translation** from Russian to English for [sprint-review-transcript.md](sprint-review-transcript.md) and drafting support for [sprint-review-summary.md](sprint-review-summary.md).
3. **GitHub Copilot Autofix powered by AI** on selected pull requests — suggestions reviewed before merge.
4. **Cursor (Composer)** for scaffolding Week 7 report structure and Moodle PDF Typst sources — human-reviewed before merge.

No LLM was used for inventing customer UAT outcomes, inventing transition-confirmation results, making merge decisions without review, or writing unreviewed pytest/QRT assertions.

## Tools

| Tool | Purpose |
| --- | --- |
| [speech2text.ru](https://speech2text.ru/) | Transcribe Sprint Review + transition confirmation recording |
| LLM translation (vendor not fixed) | English transcript and summary drafting |
| GitHub Copilot Autofix powered by AI | Suggest code fixes on PRs |
| Cursor (Grok 4.5) | Week 7 report / PDF scaffolding |

## What was produced without LLM assistance

- Timezone-safe selected-time and room-booking backend work ([#152](https://github.com/one-zero-eight/monorepo/pull/152))
- Frontend mobile / legend / selected-time UX changes demonstrated in the Sprint Review
- Customer handover and roadmap updates for MVP v3
- Sprint Review recording, customer acceptance confirmation, and UAT regression checks
- Demo Day slide deck rehearsal preparation (`When2Meet-presentation-v1-4.pdf`, Moodle only)
- Public sanitized demo video recording
- CI, secret scan, and deployment verification on `pre.innohassle.ru/when2meet`

## Review

Transcript and summary were checked against the recording before publication. Copilot and Cursor drafts were reviewed in PRs or pair review before merge. Private recording links, credentials, and identifying customer details stay in the Moodle PDF only.
