# Roadmap


## Sprint 1 — MVP v1
**Milestone:** [Sprint 1](https://github.com/one-zero-eight/monorepo/milestone/1)
**Dates:** Week 3 — 15 June 2026 to 21 June 2026

**Sprint Goal:** To release a basic working version of the service (MVP v1), which will allow organizers to create meetings and share an invitation link, and participants to mark their free time on the grid and see a general heatmap of the availability of all participants.

**Focus / expected outcome:** An end-to-end meeting availability flow is usable through a shareable link.

**Planned items:**
- [US-001](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-001) — Create a meeting
- [US-002](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-002) — Share a meeting invitation link
- [US-003](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-003) — Join through a link and submit availability
- [US-006](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-006) — View aggregated participant availability as a heatmap

## Sprint 2 — Meeting management and calendar context
**Milestone:** [Sprint 2](https://github.com/one-zero-eight/monorepo/milestone/2)
**Dates:** Week 4 — 22 June 2026 to 28 June 2026

**Sprint Goal:** Improve scheduling decisions with calendar awareness and organizer controls.

**Focus / expected outcome:** Organizers can manage participation and room booking, while participants can use calendar context when selecting availability.

**Planned items:**
- [US-004](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-004) — Calendar-event awareness while choosing times
- [US-007](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-007) — Book a room for the selected time
- [US-012](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-012) — Remove unnecessary participants
- [US-013](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-013) — Find a participant and view their availability

## Sprint 3 — Customer feedback, accessibility, and reply editing
**Milestone:** [Sprint 3](https://github.com/one-zero-eight/monorepo/milestone/3)
**Dates:** Week 5 — 29 June 2026 to 5 July 2026

**Sprint Goal:** Address Sprint Review and UAT feedback by improving the availability-selection experience, making availability intersections easier to understand, and completing participant reply editing behavior.

**Focus / expected outcome:** Participants can edit replies safely, organizers can understand availability intersections without confusing filters, and room/calendar context handles key edge cases.

**Planned items:**
- [#92](https://github.com/one-zero-eight/monorepo/issues/92) — Show personal calendar events on the availability selection grid
- [#93](https://github.com/one-zero-eight/monorepo/issues/93) — Room booking flow: explicit time selection and intersection edge cases
- [#94](https://github.com/one-zero-eight/monorepo/issues/94) — Single-button control to highlight maximum availability intersection
- [#95](https://github.com/one-zero-eight/monorepo/issues/95) — Time-slot detail view listing participants available at that slot
- [#96](https://github.com/one-zero-eight/monorepo/issues/96) — Participant list entry without selected slots must not count as availability
- [#97](https://github.com/one-zero-eight/monorepo/issues/97) — API support for editing participant availability replies
- [#98](https://github.com/one-zero-eight/monorepo/issues/98) — Define behaviour when organizer changes slots after participants already replied
- [#99](https://github.com/one-zero-eight/monorepo/issues/99) — Redesign availability grid interaction and visual design
- [#100](https://github.com/one-zero-eight/monorepo/issues/100) — Simplify intersection filter UX

## Week 6 — Trial Release And Transition Preparation
**Dates:** Week 6 — 6 July 2026 to 12 July 2026

**Course outcome focus:** Move the Sprint 3 customer-reviewed MVP v2 from feature delivery into a trial-release state that can be used by the customer on the hosted pre-production environment.

**Expected outcome:** The product remains usable at `pre.innohassle.ru/when2meet`, known Sprint Review gaps are visible, and the repository contains enough maintained evidence to support final review and handover.

**Planned work:**
- Trial-release verification for the deployed frontend, API, Swagger UI, and core meeting flow.
- Maintenance fixes for Sprint Review feedback: hide-calendar-events toggle, clearer selected-slot legend, room-booking lifecycle clarity, participant deletion confirmation, and richer participant identity display where feasible.
- Quality work: keep pytest, coverage, QRTs, CI, and secret scan green; preserve the Assignment 4 and 5 quality gates.
- Documentation work: keep interface, testing, architecture, quality, UAT, and development-process docs aligned with the actual implementation.
- Transition work: prepare customer handover boundaries, current access notes, deployment ownership notes, configuration expectations, limitations, and recovery guidance.

## Week 7 — Final MVP v3 Delivery
**Dates:** Week 7 — 13 July 2026 to 19 July 2026

**Planned release:** MVP v3, the final course delivery.

**Course outcome focus:** Deliver a final, customer-reviewable course increment without extending the roadmap into speculative post-course releases.

**Expected outcome by the end of the course:** When2Meet is ready for independent customer use on the InNoHassle pre-production deployment. The customer can create meetings, share links, collect participant availability, inspect the heatmap, use participant filters and room-booking support, and rely on maintained public documentation for current behavior, API contracts, testing, quality requirements, deployment model, limitations, and recovery expectations.

**Remaining work before final delivery:**
- Complete the final trial-release smoke check on the hosted product and API.
- Close or explicitly document remaining Sprint Review follow-ups that are not part of MVP v3.
- Confirm transition scope: repository/docs are available; runtime secrets, deployment host access, GitHub administration, and production-like operations remain with the team or InNoHassle maintainers unless explicitly transferred.
- Finalize customer handover documentation without exposing private credentials, recordings, timecodes, consent evidence, or customer-identifying data.
- Verify quality gates: relevant pytest checks, coverage gates for critical modules, QRTs, CI, secret scan, and documentation traceability.
- Update release evidence and changelog for the final MVP v3 delivery.

**End-of-course state:** The course ends with a maintained, deployed MVP v3 and documented handover status. Further customer-side operation, production ownership transfer, monitoring, rollback authority, and secret-rotation responsibility are outside the course roadmap unless separately agreed.
