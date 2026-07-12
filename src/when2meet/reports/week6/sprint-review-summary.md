# Sprint Review Summary — Sprint 4 / Week 6

**Date:** July 12, 2026

**Meeting timecodes / evidence:**

* Sprint 4 demonstration: 00:00:01–00:01:37 in [sprint-review-transcript.md](sprint-review-transcript.md).
* Final project evaluation, documentation review discussion, transition readiness, and UAT confirmation: 00:01:39–00:03:48 in [sprint-review-transcript.md](sprint-review-transcript.md).

## Participants / Roles

* **Anna Belyakova** — Customer
* **Nikita Lisitskiy** — Team representative and meeting facilitator
* **Timur Khasanov** — Product demonstrator
* **Vladislav Konovalov** — Observer

## Artifacts Demonstrated or Reviewed

* Updated meeting heatmap and final time-selection interface, linked to [#93](https://github.com/one-zero-eight/monorepo/issues/93), [#95](https://github.com/one-zero-eight/monorepo/issues/95), [#99](https://github.com/one-zero-eight/monorepo/issues/99), [US-006](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-006), and [US-007](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-007).
* Separate controls for selecting the final meeting time and booking a room, reflected in [docs/interface.md](../../docs/interface.md#update-meeting), [available rooms](../../docs/interface.md#get-available-rooms), [book room](../../docs/interface.md#book-room), and [UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time).
* Heatmap legend explaining interface elements, linked to Sprint 3 follow-up [#99](https://github.com/one-zero-eight/monorepo/issues/99), [#94](https://github.com/one-zero-eight/monorepo/issues/94), and [UAT-004](../../docs/user-acceptance-tests.md#uat-004--distinguish-my-selected-slots-on-the-availability-grid).
* Participant names displayed for selected time slots, linked to [#95](https://github.com/one-zero-eight/monorepo/issues/95), [US-013](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-013), and [ADR-0003](../../docs/architecture/adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md).
* Deployed trial release on Team 108 infrastructure: [product](https://pre.innohassle.ru/when2meet), [API / Swagger](https://api.innohassle.ru/when2meet/v0/docs).
* Customer-facing documentation set reviewed with the customer: root [README.md](../../../../README.md) (When2Meet section), [docs/customer-handover.md](../../docs/customer-handover.md), access/usage instructions, deployment notes, troubleshooting, and known limitations.
* Maintained UAT scenarios from [docs/user-acceptance-tests.md](../../docs/user-acceptance-tests.md).

## Scope or Goal Reviewed

Sprint 4 Goal: deliver a stable Week 6 trial / handover-candidate release with clearer final-time and room-booking flows, heatmap readability improvements, maintained customer-handover documentation, and transition-readiness evidence for the customer trial.

## Delivered Increment Discussed

* Final meeting time selection and room booking were separated into two independent actions ([#126](https://github.com/one-zero-eight/monorepo/issues/126), [#129](https://github.com/one-zero-eight/monorepo/issues/129), [US-007](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-007)).
* The organizer can select and save a final meeting time; the saved time is visible to all participants ([#127](https://github.com/one-zero-eight/monorepo/issues/127)).
* Room lookup, booking, change, and cancel work for the selected meeting window where the Room Booking service is available ([#128](https://github.com/one-zero-eight/monorepo/issues/128), [#130](https://github.com/one-zero-eight/monorepo/issues/130), [UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time), [UAT-006](../../docs/user-acceptance-tests.md#uat-006--change-or-cancel-a-booked-room)).
* A heatmap legend clarifies current-user selection versus aggregate availability ([#124](https://github.com/one-zero-eight/monorepo/issues/124)).
* Participant names are displayed when viewing a selected time slot ([#131](https://github.com/one-zero-eight/monorepo/issues/131)).
* Customer handover documentation describes the actual handover state ([#132](https://github.com/one-zero-eight/monorepo/issues/132)).

## UAT results

Customer-executed / customer-observed UAT against [docs/user-acceptance-tests.md](../../docs/user-acceptance-tests.md). The customer stated that the service works as expected for the trial release.

| Scenario | Result | Notes |
|---|---|---|
| UAT-001 Calendar overlay | Passed | Calendar events appear on the availability grid |
| UAT-003 Room booking | Passed | Exact-time selection, room lookup, booking, and persisted state verified |
| UAT-004 Selected-slot distinction | Passed (change request) | Legend delivered; customer asked to move it from bottom to top |
| UAT-006 Change/cancel booked room | Passed | Change, sync, and cancel verified during the trial demo |
| Overall product behaviour | Accepted | Customer stated the service works as expected |

## Customer-facing documentation review

The customer reviewed `README.md` (When2Meet entry point) and [docs/customer-handover.md](../../docs/customer-handover.md), including access, deployment, troubleshooting, and known limitations.

| Topic | Customer finding |
|---|---|
| README entry point | Matches expectations — clear product purpose, access links, and documentation routing |
| Customer handover | Matches expectations — handover scope, configuration without secrets, setup/recovery/verification are usable |
| Unclear / missing | No blocking documentation gaps identified for the reached handover level |

## Feedback

* The customer considered the demonstrated improvements successful ([transcript 00:01:37](sprint-review-transcript.md)).
* The customer stated that the project currently meets her expectations ([transcript 00:01:58–00:02:06](sprint-review-transcript.md)).
* The customer confirmed documentation review: README and customer handover match expectations.
* The heatmap legend should be placed at the top of the interface rather than at the bottom ([transcript 00:01:01](sprint-review-transcript.md), [#124](https://github.com/one-zero-eight/monorepo/issues/124) / [#99](https://github.com/one-zero-eight/monorepo/issues/99)).
* The mobile version should be validated before final release ([transcript 00:02:42](sprint-review-transcript.md)).
* The team should remain available after the course for bug fixes and possible future improvements.

## Approvals or Requested Changes

### Approvals

* Product implemented to a sufficient extent for the Week 6 trial ([transcript 00:01:39–00:01:58](sprint-review-transcript.md)).
* No major parts of the current implementation require further changes ([transcript 00:02:00–00:02:06](sprint-review-transcript.md)).
* Deployment on Team 108’s side completed; project effectively transferred to Team 108 ([transcript 00:02:13–00:02:28](sprint-review-transcript.md)).
* Customer-facing documentation (`README.md`, `docs/customer-handover.md`) accepted as matching expectations.
* UAT outcomes accepted: service works as expected for the trial release.

### Requested Changes (Sprint 5 follow-up)

* Move the heatmap legend from the bottom to the top ([#124](https://github.com/one-zero-eight/monorepo/issues/124) / [#99](https://github.com/one-zero-eight/monorepo/issues/99)).
* Fix the bug that prevents clearing the selected final meeting time when no room is booked.
* Validate the mobile version before MVP v3 release.
* Keep a lightweight post-course support channel for bugs and user-driven improvements.

## Risks

* **Functional:** Selected final meeting time currently cannot be deleted in some cases.
* **Integration:** Room-booking service was temporarily unavailable during part of the demo; end-to-end booking was verified when the service was available and through automated contract tests.
* **Release:** Mobile version still needs formal customer validation before MVP v3.
* **Support:** Post-course maintenance remains informal.

## Action Points → Sprint 5

* Allow organizers to clear or replace the selected final meeting time when no room is booked.
* Relocate the heatmap legend to the top of the interface.
* Re-test room booking after external service incidents.
* Perform mobile usability validation with the customer.
* Keep README and customer handover current through final transition.
* Track remaining feedback in [#146](https://github.com/one-zero-eight/monorepo/issues/146) / [#149](https://github.com/one-zero-eight/monorepo/issues/149).
