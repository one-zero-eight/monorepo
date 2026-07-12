# Customer Review Summary

**Date:** July 12, 2026

**Meeting timecodes / evidence:**

* Sprint 4 demonstration: 00:00:01–00:01:37 in [sprint-review-transcript.md](sprint-review-transcript.md).
* Final project evaluation and handover discussion: 00:01:39–00:03:48 in [sprint-review-transcript.md](sprint-review-transcript.md).

## Participants / Roles

* **Anna Belyakova** — Customer
* **Nikita Lisitskiy** — Team representative and meeting facilitator.
* **Timur Khasanov** — Product demonstrator.
* **Vladislav Konovalov** — Observer

## Artifacts Demonstrated or Reviewed

* Updated meeting heatmap and final time-selection interface, linked to [#93](https://github.com/one-zero-eight/monorepo/issues/93), [#95](https://github.com/one-zero-eight/monorepo/issues/95), [#99](https://github.com/one-zero-eight/monorepo/issues/99), [US-006](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-006), and [US-007](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-007).
* Separate controls for selecting the final meeting time and booking a room, reflected in [docs/interface.md](../../docs/interface.md#update-meeting), [available rooms](../../docs/interface.md#get-available-rooms), [book room](../../docs/interface.md#book-room), and [UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time).
* Heatmap legend explaining interface elements, linked to Sprint 3 follow-up [#99](https://github.com/one-zero-eight/monorepo/issues/99), [#94](https://github.com/one-zero-eight/monorepo/issues/94), and [UAT-004](../../docs/user-acceptance-tests.md#uat-004--distinguish-my-selected-slots-on-the-availability-grid).
* Participant names displayed for selected time slots, linked to [#95](https://github.com/one-zero-eight/monorepo/issues/95), [US-013](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-013), and [ADR-0003](../../docs/architecture/adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md).
* Deployed version of the application on Team 108’s infrastructure: [product](https://pre.innohassle.ru/when2meet), [API / Swagger](https://api.innohassle.ru/when2meet/v0/docs), [Week 5 deployment evidence](../week5/images/deployed-product.png), and [handover status](../../docs/customer-handover.md#handover-status).
* Repository documentation reviewed for final transition: [customer handover](../../docs/customer-handover.md), [interface](../../docs/interface.md), [testing](../../docs/testing.md), [architecture](../../docs/architecture/README.md), [roadmap](../../docs/roadmap.md#week-6--trial-release-and-transition-preparation), and [changelog](../../CHANGELOG.md#unreleased).

## Scope or Goal Reviewed

The meeting reviewed the final Sprint 4 / Week 6 trial-release improvements from the [roadmap](../../docs/roadmap.md#week-6--trial-release-and-transition-preparation): address Sprint 3 review feedback, keep the deployed product usable, and prepare evidence for final review and handover.

The reviewed changes were intended to make the final meeting scheduling flow clearer by separating final time selection from optional room booking, improving heatmap readability, and confirming transition readiness for the planned [MVP v3 final delivery](../../docs/roadmap.md#week-7--final-mvp-v3-delivery).

## Delivered Increment Discussed

* Final meeting time selection and room booking were separated into two independent actions ([#93](https://github.com/one-zero-eight/monorepo/issues/93), [US-007](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-007), [interface: update meeting](../../docs/interface.md#update-meeting), [interface: book room](../../docs/interface.md#book-room)).
* The organizer can select and save a final meeting time; the saved time is visible to all participants ([interface: EventView](../../docs/interface.md#eventview)).
* Room lookup and booking use the selected meeting window where the external Room Booking service is available ([UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time), [UAT-006](../../docs/user-acceptance-tests.md#uat-006--change-or-cancel-a-booked-room)).
* A heatmap legend was added to clarify current-user selection versus aggregate availability ([#99](https://github.com/one-zero-eight/monorepo/issues/99), [#94](https://github.com/one-zero-eight/monorepo/issues/94), [UAT-004](../../docs/user-acceptance-tests.md#uat-004--distinguish-my-selected-slots-on-the-availability-grid)).
* Participant names are now displayed when viewing a selected time slot ([#95](https://github.com/one-zero-eight/monorepo/issues/95), [US-013](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-013)).
* The application has been deployed on Team 108’s side ([customer handover: public entry points](../../docs/customer-handover.md#current-status), [deployment evidence](../week5/images/deployed-product.png)).
* The project has been prepared for transfer to Team 108 through maintained [handover](../../docs/customer-handover.md), [testing](../../docs/testing.md), [quality](../../docs/quality-requirements.md), [architecture](../../docs/architecture/README.md), and [release](../../CHANGELOG.md#unreleased) documentation.

## Feedback

* The customer considered the demonstrated improvements successful ([transcript 00:01:37](sprint-review-transcript.md)).
* The customer stated that the project currently meets her expectations ([transcript 00:01:58-00:02:06](sprint-review-transcript.md)).
* The heatmap legend should be placed at the top of the interface rather than at the bottom ([transcript 00:01:01](sprint-review-transcript.md), [#99](https://github.com/one-zero-eight/monorepo/issues/99)).
* The mobile version should be tested before the product is released ([transcript 00:02:42](sprint-review-transcript.md), [UAT-001](../../docs/user-acceptance-tests.md#uat-001--choose-a-meeting-time-with-calendar-event-awareness), [Week 7 release checklist](../../docs/roadmap.md#week-7--final-mvp-v3-delivery)).
* The team should remain available after the course to support bug fixing and possible future user-driven improvements ([customer handover: remaining support](../../docs/customer-handover.md#handover-status)).
* `README.md` and [Customer Handover](../../docs/customer-handover.md) still need customer/developer evaluation for completeness, clarity, and usefulness.

## Approvals or Requested Changes

### Approvals

* The customer confirmed that the project had been implemented to a sufficient extent ([transcript 00:01:39-00:01:58](sprint-review-transcript.md)).
* The customer stated that no major parts of the current implementation required further changes ([transcript 00:02:00-00:02:06](sprint-review-transcript.md)).
* The customer approved the overall product state for the Week 6 trial-release milestone ([roadmap](../../docs/roadmap.md#week-6--trial-release-and-transition-preparation)).
* The customer confirmed that deployment on Team 108’s side had been completed ([transcript 00:02:13-00:02:28](sprint-review-transcript.md), [handover scope](../../docs/customer-handover.md#handover-scope)).
* The customer confirmed that the project had effectively been handed over to Team 108 ([handover status](../../docs/customer-handover.md#handover-status)).
* The customer indicated that the product could be released if the mobile version works correctly ([roadmap: MVP v3](../../docs/roadmap.md#week-7--final-mvp-v3-delivery)).

### Requested Changes

* Move the heatmap legend from the bottom of the interface to the top ([#99](https://github.com/one-zero-eight/monorepo/issues/99), [UAT-004](../../docs/user-acceptance-tests.md#uat-004--distinguish-my-selected-slots-on-the-availability-grid)).
* Fix the bug that prevents the organizer from deleting or clearing the selected final meeting time ([interface: selected time constraint](../../docs/interface.md#update-meeting)).
* Test and validate the mobile version before release ([UAT-001](../../docs/user-acceptance-tests.md#uat-001--choose-a-meeting-time-with-calendar-event-awareness), [Week 7 remaining work](../../docs/roadmap.md#week-7--final-mvp-v3-delivery)).
* Review and, where necessary, improve `README.md` and [Customer Handover](../../docs/customer-handover.md).
* Maintain a communication channel for post-course bug fixes and future improvements ([customer handover: remaining support](../../docs/customer-handover.md#handover-status)).

## Risks

* **Functional risk:** The selected final meeting time currently cannot be deleted, which may prevent organizers from correcting an accidental or outdated selection ([interface: update meeting](../../docs/interface.md#update-meeting)).
* **Integration / availability risk:** The room-booking service was temporarily unavailable during the demonstration, so the updated end-to-end booking flow could not be fully verified live ([UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time), [UAT-006](../../docs/user-acceptance-tests.md#uat-006--change-or-cancel-a-booked-room)).
* **Release risk:** The mobile version has not yet been formally validated by the customer ([roadmap: final MVP v3 delivery](../../docs/roadmap.md#week-7--final-mvp-v3-delivery)).
* **Documentation risk:** The completeness and clarity of the handover documentation have not yet been confirmed by the customer ([customer handover](../../docs/customer-handover.md)).
* **Support risk:** No formal post-course maintenance arrangement was defined, although the customer expects the team to remain available for bug fixing and future improvements ([handover status](../../docs/customer-handover.md#handover-status)).

## Action Points

* Fix the issue that prevents deletion of the selected final meeting time ([interface: update meeting](../../docs/interface.md#update-meeting)).
* Move the heatmap legend to the top of the interface ([#99](https://github.com/one-zero-eight/monorepo/issues/99)).
* Re-test the room-booking flow when the external booking service becomes available ([UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time), [interface: book room](../../docs/interface.md#book-room)).
* Perform mobile usability and functional testing ([UAT-001](../../docs/user-acceptance-tests.md#uat-001--choose-a-meeting-time-with-calendar-event-awareness)).
* Provide the mobile version to the customer for final validation ([roadmap: Week 7](../../docs/roadmap.md#week-7--final-mvp-v3-delivery)).
* Review `README.md` for completeness and developer onboarding clarity.
* Review [Customer Handover](../../docs/customer-handover.md) for completeness and suitability for Team 108.
* Define how the team will handle post-course bug reports and future support requests ([customer handover: remaining support](../../docs/customer-handover.md#handover-status)).

## Resulting Product Backlog or Scope Changes

* **Bug fix:** Allow an organizer to remove or replace the selected final meeting time ([interface: EventView selected_time](../../docs/interface.md#eventview)).
* **UI/UX update:** Relocate the heatmap legend to the top of the interface ([#99](https://github.com/one-zero-eight/monorepo/issues/99), [#94](https://github.com/one-zero-eight/monorepo/issues/94)).
* **Quality assurance:** Add mobile-version validation to the release checklist ([UAT-001](../../docs/user-acceptance-tests.md#uat-001--choose-a-meeting-time-with-calendar-event-awareness), [roadmap: Week 7](../../docs/roadmap.md#week-7--final-mvp-v3-delivery)).
* **Integration validation:** Add an end-to-end room-booking regression test after the external service is restored ([US-007](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-007), [#93](https://github.com/one-zero-eight/monorepo/issues/93), [UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time)).
* **Documentation:** Complete the review and revision of `README.md` and [Customer Handover](../../docs/customer-handover.md).
* **Operational scope:** Add a lightweight post-handover support and bug-fixing process ([handover status](../../docs/customer-handover.md#handover-status)).
* **Release scope:** Treat successful mobile validation as the remaining condition for product release ([MVP v3 release scope](../../docs/roadmap.md#week-7--final-mvp-v3-delivery)).
