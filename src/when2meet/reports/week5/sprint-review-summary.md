# Customer Review Summary

**Date:** 2026-07-05

**Participants / roles:**

- Customer (stakeholder)
- Vladislav Konovalov (team representative / Sprint increment demo)
- Timur Khasanov (observer)

**Scope or goal reviewed:**

Sprint 3 reviewed the Week 5 goal from the [roadmap](../../docs/roadmap.md#sprint-3--customer-feedback-accessibility-and-reply-editing): address Sprint Review and UAT feedback by improving availability selection, making intersections easier to understand, and completing participant reply editing behavior.

**Artifacts demonstrated:**

- Meeting creation and editing flow with day/time-slot selection.
- Personal calendar overlay during slot selection, including hover details and mobile visibility.
- Meeting screen with participant responses, selected personal availability, participant filtering, and selected-slot border.
- Heatmap-based room booking flow through InNoHassle.
- Participant search, individual availability filtering, and owner-side participant removal.
- UAT scenarios from [docs/user-acceptance-tests.md](../../docs/user-acceptance-tests.md).
- Interface evidence in [docs/interface.md](../../docs/interface.md).
- Architecture evidence in [docs/architecture/README.md](../../docs/architecture/README.md), especially Calendar API and Room Booking API integration boundaries.

**Delivered increment discussed:**

- Calendar events are shown while selecting meeting availability, including event details and mobile support ([#92](https://github.com/one-zero-eight/monorepo/issues/92), [US-004](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-004)).
- Users can still choose slots that overlap their calendar; the overlay is informational, not blocking.
- Participant list is more compact and searchable, and owners can remove participants ([#95](https://github.com/one-zero-eight/monorepo/issues/95), [US-012](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-012), [US-013](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-013)).
- Availability grid now visually distinguishes the current user's selected slots with a border.
- Minimum-participant filtering was demonstrated as a way to narrow visible slots ([#100](https://github.com/one-zero-eight/monorepo/issues/100)).
- Room booking from the heatmap was demonstrated, including free-room selection and reservation confirmation ([#93](https://github.com/one-zero-eight/monorepo/issues/93), [US-007](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-007)).

**UAT results:**

| Scenario | Result | Notes |
|---|---|---|
| Calendar overlay while selecting time | Passed with change request | Events and details are visible on desktop and mobile; customer requested a hide-calendar-events toggle |
| Participant search and availability filtering | Passed with change request | Search and filtering work; customer disliked email-only display and requested safer participant deletion |
| Room booking for selected time | Partial | Free-room selection works, but the flow is unclear and calendar push/linking are incomplete |

**Feedback:**

- Add a control to hide personal calendar events when they distract the user.
- Add a legend or clearer visual explanation for "my selected time" versus aggregate availability.
- Clarify the room-booking page state and make booking optional after choosing a meeting time.
- Replace the native-looking room dropdown or align it with the rest of the application design.
- Add a meeting link to the created calendar event.
- Push the final meeting event to all available participants' calendars, not only the creator's calendar.
- Improve participant identity display; email-only participant rows were not accepted as polished UX.
- Add confirmation before deleting/removing a participant.

**Approvals or requested changes:**

- **Approved:** calendar overlay visibility, including mobile support.
- **Approved:** informational conflict handling; users may still select busy slots.
- **Approved:** participant search and availability filtering.
- **Approved with changes:** selected-slot border, only if supported by a legend or clearer visual cue.
- **Approved with changes:** room booking, only after the flow explains the selected time, optional booking, room reservation, and calendar event creation.
- **Requested:** hide-calendar-events toggle, participant deletion confirmation, better participant names, calendar event link, and calendar push to all available participants.

**Risks:**

- Calendar overlay may distract users who do not follow their InNoHassle calendar unless the hide toggle is added.
- Selected-slot border can be misread without a legend, causing incorrect interpretation of the heatmap.
- Room booking and meeting/event creation are still loosely connected; this can create reservations without a clear meeting lifecycle.
- Calendar synchronization is incomplete because booked meetings are not yet pushed to all available participants.
- Email-only participant display and missing deletion confirmation can reduce customer trust in participant management.

**Action points -> backlog:**

| Action | Backlog / evidence |
|---|---|
| Add hide-calendar-events toggle | Extend [#92](https://github.com/one-zero-eight/monorepo/issues/92) |
| Add legend for current user's selected slots | Extend [#99](https://github.com/one-zero-eight/monorepo/issues/99) / [#94](https://github.com/one-zero-eight/monorepo/issues/94) |
| Clarify room-booking flow and optionality | Extend [#93](https://github.com/one-zero-eight/monorepo/issues/93) |
| Align room selector styling with product UI | Extend [#99](https://github.com/one-zero-eight/monorepo/issues/99) |
| Add meeting link to calendar event | New backlog item under Sprint 3 follow-up scope |
| Push calendar event to all available participants | New backlog item linked to [#93](https://github.com/one-zero-eight/monorepo/issues/93) and Calendar API integration |
| Show participant names/profile data instead of email-only rows | Link to [ADR-0003](../../docs/architecture/adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md) and add UX follow-up |
| Confirm participant removal before deletion | Extend [US-012](https://github.com/one-zero-eight/monorepo/issues?q=is%3Aissue%20US-012) / [#99](https://github.com/one-zero-eight/monorepo/issues/99) |

**Resulting backlog or scope changes:**

- Sprint 3 scope remains focused on calendar context, participant management, intersection clarity, and room booking, but calendar push and room-booking lifecycle integration became required follow-up work.
- [#92](https://github.com/one-zero-eight/monorepo/issues/92) is accepted as delivered only with the added hide-toggle refinement.
- [#93](https://github.com/one-zero-eight/monorepo/issues/93) remains partial until room booking is linked to meeting creation, calendar event links, and participant calendar push.
- [#99](https://github.com/one-zero-eight/monorepo/issues/99) gains concrete UX tasks: selected-slot legend, room selector styling, clearer booking state, and participant deletion confirmation.
- Architecture evidence to keep current: [static/dynamic/deployment views](../../docs/architecture/README.md#views), [ADR-0003](../../docs/architecture/adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md), and interface docs for event, participant, calendar, and room-booking behavior.
