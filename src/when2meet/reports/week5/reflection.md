## Learning points

- Documenting architecture with three views and ADRs made integration boundaries (Accounts, Calendar API, Room Booking API, MongoDB) explicit before adding more customer-facing changes.
- Sprint Review showed that delivering calendar overlay ([#92](https://github.com/one-zero-eight/monorepo/issues/92)) is not enough without a hide toggle and clearer selected-slot legend ([#99](https://github.com/one-zero-eight/monorepo/issues/99)).
- Room booking and meeting lifecycle must be explained as one flow; partial room reservation without calendar push erodes customer trust ([#93](https://github.com/one-zero-eight/monorepo/issues/93)).
- QR-004 / QRT-004 keep Assignment 4 gates active while architecture and QA docs evolve together.

## Validated assumptions

- A React SPA behind the InNoHassle edge can deliver MVP v2 UX improvements without rewriting the backend service shape.
- Customer-executed UAT in the same recording as Sprint Review produces actionable backlog updates faster than internal-only demos.
- Repository-hosted transcript and summary artifacts (`sprint-review-transcript.md`, `sprint-review-summary.md`) are easier to review than ad-hoc notes.

## Friction and gaps

- [#97](https://github.com/one-zero-eight/monorepo/issues/97) remains blocked on a cross-service reply-editing endpoint.
- Room booking UAT stayed partial because page state, optional booking, and calendar push are incomplete.
- Email-only participant rows and missing deletion confirmation were flagged as unacceptable polish gaps.
- GitHub Pages deploy required a `gh-pages` branch workaround after `actions/deploy-pages` failed intermittently.

## Planned response

- **Product:** Close follow-ups on hide-calendar toggle, booking lifecycle clarity, calendar push, participant names, and deletion confirmation.
- **Architecture:** Keep [docs/architecture/README.md](../../docs/architecture/README.md) and ADRs current when Calendar or Room Booking contracts change.
- **Quality:** Keep QRT-001–004, secret scan, and coverage gates active for every Sprint PBI.
- **Process:** Publish SemVer release `v0.2.0` from protected `main` and refresh Week 5 evidence screenshots after release creation.
