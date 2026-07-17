# Changelog

All notable user-visible changes to the When2Meet service are documented here.
Releases follow [SemVer](https://semver.org/) and map to MVP increments.

## [Unreleased]

### Documentation

- Updated roadmap, customer handover, Week 7 UAT summary, and Week 7 final report for MVP v3 course delivery ([#156](https://github.com/one-zero-eight/monorepo/issues/156), [#160](https://github.com/one-zero-eight/monorepo/issues/160), [#166](https://github.com/one-zero-eight/monorepo/issues/166)).
- Extended Sprint 5 quality and CI evidence links for When2Meet testing, QRTs, secret scan, and link-check gates ([#167](https://github.com/one-zero-eight/monorepo/issues/167)).

### Planned for MVP v3 (Sprint 5 / Week 7)

- Move heatmap legend to the top of the interface.
- Allow clearing or replacing the selected final meeting time when no room is booked.
- Mobile validation with the customer before final release.

## [0.3.0] — Week 6 Trial Release (Sprint 4 / Assignment 6)

**Release date:** 2026-07-12
**Sprint milestone:** [Sprint 4](https://github.com/one-zero-eight/monorepo/milestone/4)
**Week 6 report:** [reports/week6/README.md](reports/week6/README.md)
**Customer handover:** [docs/customer-handover.md](docs/customer-handover.md)

Week 6 trial / handover-candidate release for Assignment 6. Deployed at [pre.innohassle.ru/when2meet](https://pre.innohassle.ru/when2meet).

### Added

- Selected meeting time persistence and display for organizers and participants ([#126](https://github.com/one-zero-eight/monorepo/issues/126), [#127](https://github.com/one-zero-eight/monorepo/issues/127)).
- Room booking lifecycle: list available rooms, book, show booked room, change, and cancel ([#128](https://github.com/one-zero-eight/monorepo/issues/128), [#129](https://github.com/one-zero-eight/monorepo/issues/129), [#130](https://github.com/one-zero-eight/monorepo/issues/130)).
- Heatmap legend distinguishing personal selection from aggregate availability ([#124](https://github.com/one-zero-eight/monorepo/issues/124)).
- Participant / event names on overlapping timeslots ([#131](https://github.com/one-zero-eight/monorepo/issues/131)).
- Customer handover documentation covering access, deployment, configuration, recovery, verification, limitations, and handover status ([#132](https://github.com/one-zero-eight/monorepo/issues/132)).
- Root README When2Meet entry point with product status, access links, and maintained documentation links.

### Changed

- Separated final meeting-time selection from optional room booking controls ([#125](https://github.com/one-zero-eight/monorepo/issues/125)).
- Roadmap updated for Sprint 4 trial release and Sprint 5 / MVP v3 final delivery.

### Known gaps after Sprint 4 Review

- Move heatmap legend to the top; allow clearing selected final time; validate mobile before MVP v3 (see [sprint-review-summary.md](reports/week6/sprint-review-summary.md)).

## [0.2.0] — MVP v2 (Sprint 3 / Assignment 5)

**Release date:** 2026-07-05
**Sprint milestone:** [Sprint 3](https://github.com/one-zero-eight/monorepo/milestone/3)

### Added

- Personal calendar overlay while selecting meeting availability, including mobile event details ([#92](https://github.com/one-zero-eight/monorepo/issues/92)).
- Maintained architecture documentation (static, dynamic, deployment views) and ADRs 0001–0003.
- `docs/development-process.md` with git workflow and configuration-management rules.
- QR-004 / QRT-004 QA and architecture traceability gate ([#108](https://github.com/one-zero-eight/monorepo/pull/108)).
- Hosted documentation site on GitHub Pages.
- Participant search, individual availability filtering, and owner-side participant removal improvements ([#95](https://github.com/one-zero-eight/monorepo/issues/95), [US-012](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-012), [US-013](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-013)).

### Changed

- Availability grid distinguishes the current user's selected slots with a border ([#99](https://github.com/one-zero-eight/monorepo/issues/99)).
- Minimum-participant filtering narrows visible slots on the heatmap ([#100](https://github.com/one-zero-eight/monorepo/issues/100)).
- Room booking from the heatmap supports free-room selection and reservation confirmation ([#93](https://github.com/one-zero-eight/monorepo/issues/93)).
- Organizer slot-grid edits preserve hidden participant availability ([#98](https://github.com/one-zero-eight/monorepo/issues/98) / [#106](https://github.com/one-zero-eight/monorepo/pull/106)).
- Frontend stack documented as a **React** SPA (architecture correction).

### Fixed

- Slot-edit policy: removed organizer slots stay in stored participant replies until explicitly discarded.

### Known gaps after Sprint Review

- Hide-calendar-events toggle, selected-slot legend, clearer room-booking lifecycle, calendar push to all participants, participant deletion confirmation, and richer participant identity display remain follow-up work (see [sprint-review-summary.md](reports/week5/sprint-review-summary.md)).

## [0.1.0] — MVP v1 (Sprint 1 / Assignment 3)

**Release date:** 2026-06-21
**Sprint milestone:** [Sprint 1](https://github.com/one-zero-eight/monorepo/milestone/1)

### Added

- End-to-end meeting creation, shareable invitation links, participant availability submission, and heatmap view.
- Short slug-based public event references and InNoHassle SSO integration.

## [0.0.1] — MVP v0 (Assignment 2)

Initial prototype increment with hosted frontend and API smoke-check paths.
