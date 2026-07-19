# Sprint Review Summary — Sprint 5 / Week 7

**Date:** July 19, 2026

**Meeting timecodes / evidence:**

* MVP v3 demonstration and mobile usability review: 00:00:02–00:03:45 in [sprint-review-transcript.md](sprint-review-transcript.md).
* Final acceptance, release approval, handover, and support discussion: 00:03:55–00:05:56 in [sprint-review-transcript.md](sprint-review-transcript.md).

## Participants / Roles

* **Anna Belyakova** — Customer
* **Nikita Lisitckii** — Team representative and meeting facilitator
* **Mikhail Istomin** — Product demonstrator
* **Timur Khasanov** — Observer
* **Vladislav Konovalov** — Observer
* **Dmitrii Chudin** — Observer

## Artifacts Demonstrated or Reviewed

* Final **MVP v3** desktop and mobile meeting-creation experience, delivered under the [Sprint 5 milestone](https://github.com/one-zero-eight/monorepo/milestone/5) and summarized in the [Week 7 final report](README.md).
* Hosted release on Team 108 / InNoHassle infrastructure: [product](https://pre.innohassle.ru/when2meet), [API / Swagger](https://api.innohassle.ru/when2meet/v0/docs), and [hosted documentation](https://one-zero-eight.github.io/monorepo/).
* Mobile scrolling and time-slot selection changes, reviewed against the Sprint 4 follow-ups in [#146](https://github.com/one-zero-eight/monorepo/issues/146) and [#149](https://github.com/one-zero-eight/monorepo/issues/149).
* Selected-slot distinction and heatmap legend, traced through [#99](https://github.com/one-zero-eight/monorepo/issues/99), [#124](https://github.com/one-zero-eight/monorepo/issues/124), and [UAT-004](../../docs/user-acceptance-tests.md#uat-004--distinguish-my-selected-slots-on-the-availability-grid).
* Final selected-time and room-booking behavior, including explicit timezone handling from [#152](https://github.com/one-zero-eight/monorepo/pull/152), [API interface artifacts](../../docs/interface.md), and [UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time).
* Final transition evidence: [roadmap](../../docs/roadmap.md), [customer handover](../../docs/customer-handover.md), [UAT results](../../docs/user-acceptance-tests.md), and [MVP v3 documentation delivery](https://github.com/one-zero-eight/monorepo/pull/190).

## Scope or Goal Reviewed

Sprint 5 goal: incorporate Week 6 feedback, validate the final desktop and mobile experience, complete MVP v3, and transition the product and maintained documentation to Team 108 / InNoHassle. The final scope is recorded in the [roadmap](../../docs/roadmap.md) and [changelog](../../CHANGELOG.md).

## Delivered Increment Discussed

* Mobile scrolling and slot selection were improved and demonstrated on the meeting-creation flow.
* Selected meeting times preserve an explicit timezone offset through available-room lookup and booking ([#152](https://github.com/one-zero-eight/monorepo/pull/152), [UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time)).
* The final MVP retains meeting creation, sharing, participant availability, heatmap review, selected-time persistence, and the room-booking lifecycle ([Week 7 report](README.md)).
* Handover, UAT, testing, quality, architecture, deployment, and recovery documentation were consolidated for final delivery ([#156](https://github.com/one-zero-eight/monorepo/issues/156), [#160](https://github.com/one-zero-eight/monorepo/issues/160), [#166](https://github.com/one-zero-eight/monorepo/issues/166), [#167](https://github.com/one-zero-eight/monorepo/issues/167)).

## Feedback

* On mobile, selecting a slot can still require scrolling to see the resulting information, causing the user to lose visual context ([transcript 00:01:51–00:02:16](sprint-review-transcript.md)).
* Double-click-and-drag slot selection is not sufficiently intuitive and should be reconsidered as post-course UX work ([transcript 00:02:23–00:02:55](sprint-review-transcript.md)).
* The legend must be visible above the response heatmap and clearly explain the purple shades on both mobile and desktop ([transcript 00:02:55–00:03:45](sprint-review-transcript.md), [#124](https://github.com/one-zero-eight/monorepo/issues/124), [UAT-004](../../docs/user-acceptance-tests.md#uat-004--distinguish-my-selected-slots-on-the-availability-grid)).
* No additional major functional gaps were identified; the customer characterized the remaining items as minor ([transcript 00:04:16–00:04:35](sprint-review-transcript.md)).

## Approvals or Requested Changes

### Approvals

* The customer approved the project as ready for release and complete against its stated functionality ([transcript 00:03:55–00:04:12](sprint-review-transcript.md)).
* The customer approved handling the remaining minor UI changes outside the SWP course ([transcript 00:04:16–00:04:35](sprint-review-transcript.md)).
* The customer confirmed deployment on InNoHassle infrastructure and handover to Team 108 ([transcript 00:04:38–00:05:06](sprint-review-transcript.md), [customer handover](../../docs/customer-handover.md)).

### Requested Post-Course Changes

* Keep interaction results within the active mobile viewport.
* Move the heatmap legend above the response grid and make its labels unambiguous on desktop and mobile.
* Replace or refine double-click-and-drag slot selection with a more discoverable interaction.

## Risks

* **Usability:** Double-click-and-drag selection and viewport movement can make slot selection difficult on touch devices.
* **Accessibility / comprehension:** A color-dependent heatmap without immediately visible labels can be misinterpreted.
* **Operations:** Deployment access, secrets, monitoring, rollback authority, and production ownership remain with Team 108 / InNoHassle maintainers as described in the [handover boundaries](../../docs/customer-handover.md#handover-status).
* **Support:** Post-course maintenance depends on continued Team 108 ownership and prioritization of user feedback.

## Action Points and Resulting Backlog

* Treat viewport-local feedback, legend placement and labeling, and slot-selection redesign as customer-driven post-course UI enhancements; retain traceability to [#99](https://github.com/one-zero-eight/monorepo/issues/99), [#124](https://github.com/one-zero-eight/monorepo/issues/124), [#146](https://github.com/one-zero-eight/monorepo/issues/146), and [#149](https://github.com/one-zero-eight/monorepo/issues/149).
* Keep [README.md](../../../../README.md), [customer-handover.md](../../docs/customer-handover.md), and the [Week 7 final report](README.md) current as ownership or operational access changes.
* Team 108 maintainers continue listening to user feedback, fixing bugs, and evaluating relevant feature ideas under the support expectations stated at [00:05:12–00:05:37](sprint-review-transcript.md).
* No additional course-scope increment was opened: MVP v3 remains the final course release, with optional polish continuing after handover.
