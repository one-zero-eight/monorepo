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

## Sprint 4 — Week 6 Trial Release And Transition Preparation
**Milestone:** [Sprint 4](https://github.com/one-zero-eight/monorepo/milestone/4)
**Dates:** Week 6 — 6 July 2026 to 12 July 2026

**Sprint Goal:** Deliver a stable Week 6 trial / handover-candidate release with clearer final-time and room-booking flows, heatmap readability improvements, maintained customer-handover documentation, and transition-readiness evidence for the customer trial.

**Focus / expected outcome:** Customer can trial the hosted product at `pre.innohassle.ru/when2meet`, customer-facing docs are reviewed, and Week 7 follow-up is explicit.

**Selected Sprint PBIs (examples):**
- [#124](https://github.com/one-zero-eight/monorepo/issues/124) — Heatmap legend
- [#125](https://github.com/one-zero-eight/monorepo/issues/125) — Rename Book Room / timeslot UX
- [#126](https://github.com/one-zero-eight/monorepo/issues/126) / [#127](https://github.com/one-zero-eight/monorepo/issues/127) — Selected meeting time
- [#128](https://github.com/one-zero-eight/monorepo/issues/128)–[#130](https://github.com/one-zero-eight/monorepo/issues/130) — Room booking lifecycle
- [#131](https://github.com/one-zero-eight/monorepo/issues/131) — Event / participant names on slots
- [#132](https://github.com/one-zero-eight/monorepo/issues/132) — Customer handover documentation
- [#150](https://github.com/one-zero-eight/monorepo/issues/150) — Sprint 4 Review and Week 6 outcomes

**Status after Week 6:** Trial release delivered and customer-reviewed. Documentation (`README.md`, `docs/customer-handover.md`) accepted. UAT critical flows accepted. Follow-ups: legend top placement, selected-time clear, mobile validation.

## Sprint 5 — Final MVP v3 Delivery
**Milestone:** [Sprint 5](https://github.com/one-zero-eight/monorepo/milestone/5)
**Dates:** Week 7 — 13 July 2026 to 19 July 2026

**Sprint Goal:** Use Week 6 trial feedback to complete follow-up maintenance, confirm final transition, and deliver the final course version `MVP v3`.

**Planned release:** MVP v3, the final course delivery.

**Expected follow-up scope (depends on Week 6 feedback):**
- [#146](https://github.com/one-zero-eight/monorepo/issues/146) — Convert Week 6 trial feedback and blockers into Sprint 5 PBIs
- Move heatmap legend to the top; allow clearing selected final meeting time; mobile validation
- Final transition confirmation and customer-confirmation status for `docs/customer-handover.md`
- Final SemVer release mapped to MVP v3 and public sanitized demo video

**Expected outcome by the end of the course:** When2Meet is ready for independent customer use on the InNoHassle pre-production deployment, with maintained documentation for behavior, API contracts, testing, quality requirements, deployment model, limitations, and recovery expectations.

**End-of-course state:** The course ends with a maintained, deployed MVP v3 and documented handover status. Further customer-side operation, production ownership transfer, monitoring, rollback authority, and secret-rotation responsibility are outside the course roadmap unless separately agreed.
