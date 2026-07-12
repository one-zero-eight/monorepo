# User Acceptance Tests

Maintained end-user-facing acceptance scenarios for When2Meet. Customer execution results and scenarios awaiting execution are recorded below without private customer-identifying details.

## UAT-001 — Choose a meeting time with calendar-event awareness

**Traceability:** US-004
**Role:** Meeting participant
**Status:** Active
**Result (Week 4):** Not executed — reverse calendar overlay not implemented in this increment
**Result (Week 5):** Passed with change request — overlay works on desktop and mobile; customer requested hide-calendar toggle
**Result (Week 6):** Passed — InNoHassle Calendar events appear in the corresponding availability-grid time slots
**Executed by:** Lisitskii Nikita (demo)
**Execution date:** 2026-07-12
**Evidence:** [Sprint Review transcript](https://github.com/one-zero-eight/monorepo/blob/main/src/when2meet/reports/week5/sprint-review-transcript.md); private recording (Moodle only)

### Preconditions

- A test participant has an existing calendar event on Tuesday from 10:00 to 11:00.
- The participant has received a meeting invitation with an availability grid that includes Tuesday from 09:00 to 12:00.

### Steps

1. Open the meeting invitation.
2. View the availability grid.
3. Verify that the existing calendar event is marked at Tuesday 10:00–11:00.
4. Select availability for a time slot that overlaps the calendar event.
5. View the meeting heatmap or availability summary.

### Expected result

- InNoHassle Calendar events are visible on their relevant time slots when the grid opens.
- Selecting a conflicting time remains possible, but the system clearly indicates that it conflicts with the participant's calendar event.

### Feedback

- The requested reverse calendar integration now displays InNoHassle Calendar events on the time grid → [#92](https://github.com/one-zero-eight/monorepo/issues/92).
- The hide-calendar-events toggle remains a separate follow-up from the Week 5 change request.

### History

| Date | Version | Result | Notes |
|---|---|---|---|
| 2026-07-12 | Trial release | Passed | InNoHassle Calendar events displayed in the availability grid |
| 2026-07-05 | 2.0 | Passed (change request) | Hide-calendar toggle requested |
| 2026-06-27 | 1.0 | Not executed | Reverse calendar integration deferred to backlog |
| — | 1.0 | Not executed | Initial scenario |

---

## UAT-002 — Find a participant, review availability, and remove them from a meeting

**Traceability:** US-012; US-013
**Role:** Meeting organizer
**Status:** Active
**Result (Week 4):** Passed (participant search); removal flow not exercised in recorded session
**Result (Week 5):** Passed with change request — search and filtering work; email-only participant rows and missing deletion confirmation flagged
**Executed by:** Vladislav Konovalov (demo); customer observed UAT segment
**Execution date:** 2026-07-05
**Evidence:** [Sprint Review transcript](https://github.com/one-zero-eight/monorepo/blob/main/src/when2meet/reports/week5/sprint-review-transcript.md); private recording (Moodle only)

### Preconditions

- A meeting contains at least three participants with submitted availability.
- At least one participant name is searchable on the meeting grid.

### Steps

1. Open the meeting's participant list.
2. Enter part of a participant name into the search field.
3. Select the participant from filtered results.
4. Verify that the participant's availability is displayed on the meeting time grid.

### Expected result

- Searching by part of a participant's name shows matching participants.
- Selecting a participant shows their availability on the meeting grid.

### Feedback

- Search worked without issues during customer-executed UAT.
- Customer noted that participants who appear in the list without selecting a time should not count as having answered → [#96](https://github.com/one-zero-eight/monorepo/issues/96).

### History

| Date | Version | Result | Notes |
|---|---|---|---|
| 2026-07-05 | 2.0 | Passed (change request) | Deletion confirmation and richer identity display requested |
| 2026-06-27 | 1.0 | Passed (search) | Removal steps not run in recorded UAT |
| — | 1.0 | Not executed | Initial scenario |

---

## UAT-003 — Book an available room for a selected meeting time

**Traceability:** US-007; [#126](https://github.com/one-zero-eight/monorepo/issues/126); [#128](https://github.com/one-zero-eight/monorepo/issues/128); [#129](https://github.com/one-zero-eight/monorepo/issues/129)
**Role:** Meeting organizer
**Status:** Active
**Result (Week 4):** Partial — modal and room list work; explicit booking time not confirmed
**Result (Week 5):** Partial — free-room selection works; booking state, optional flow, calendar link, and participant calendar push incomplete
**Result (Week 6):** Passed — exact meeting-time selection, eligible-room lookup, booking, and persisted booking state work as expected
**Executed by:** Lisitskii Nikita (demo)
**Execution date:** 2026-07-12
**Evidence:** [Sprint Review transcript](https://github.com/one-zero-eight/monorepo/blob/main/src/when2meet/reports/week5/sprint-review-transcript.md); [API contract](interface.md#book-room); [automated contract tests](../../../tests/when2meet/test_events.py); private recording (Moodle only)

### Preconditions

- A meeting has participant availability on the grid.
- The organizer has selected an exact start and end time for the meeting.
- At least one room is available in the test environment.

### Steps

1. Open the meeting details and review participant availability.
2. Select an exact meeting start and end time.
3. Select **Book a room**.
4. Review the rooms that are free and bookable for the complete selected time window.
5. Select one available room and confirm.
6. Reload the meeting details.

### Expected result

- The organizer sees rooms available for the selected meeting time.
- Rooms that are busy, unavailable for part of the selected window, or not bookable by the organizer are excluded.
- The confirmed reservation uses the selected meeting start and end time.
- The meeting details retain the booked room and booking reference after reload.
- A second booking attempt is rejected while the meeting already has a booked room.

### Feedback

- Customer asked which reservation time is used; team acknowledged the flow must ask explicitly and handle multiple/zero intersection edge cases → [#93](https://github.com/one-zero-eight/monorepo/issues/93).
- Week 6 work added explicit selected meeting time, availability checks through Room Booking, persistent booking state, and concurrent-booking protection.

### History

| Date | Version | Result | Notes |
|---|---|---|---|
| 2026-07-12 | Trial release | Passed | Exact-time room booking lifecycle verified during demo |
| 2026-07-05 | 2.0 | Partial | Room reservation works; lifecycle and calendar push incomplete |
| 2026-06-27 | 1.0 | Partial | Room modal works; time-selection logic incomplete |
| — | 1.0 | Not executed | Initial scenario |

---

## UAT-004 — Distinguish my selected slots on the availability grid

**Traceability:** [#99](https://github.com/one-zero-eight/monorepo/issues/99); [#94](https://github.com/one-zero-eight/monorepo/issues/94)
**Role:** Meeting participant / organizer
**Status:** Active
**Result (Week 5):** Passed with change request — border visible; customer requested a legend
**Executed by:** Vladislav Konovalov (demo); customer observed UAT segment
**Execution date:** 2026-07-05
**Evidence:** [Sprint Review summary](../reports/week5/sprint-review-summary.md); private recording (Moodle only)

### Preconditions

- A meeting has multiple participants with submitted availability.
- The user opens the hosted MVP v2 grid.

### Steps

1. Open the meeting availability view.
2. Select personal availability on one or more slots.
3. Verify selected slots are visually distinct from aggregate heatmap fill.
4. Review whether the distinction is understandable without relying on color alone.

### Expected result

- The current user's selected slots are clearly distinguishable.
- The distinction remains understandable for organizers and participants reviewing the grid.

### Feedback

- Customer approved the border approach only with an added legend explaining “my time” vs aggregate availability.

### History

| Date | Version | Result | Notes |
|---|---|---|---|
| 2026-07-05 | 2.0 | Passed (change request) | Legend requested |
| — | 2.0 | Not executed | Initial scenario for MVP v2 |

---

## UAT-005 — Filter visible slots by minimum participant count

**Traceability:** [#100](https://github.com/one-zero-eight/monorepo/issues/100)
**Role:** Meeting organizer
**Status:** Active
**Result (Week 5):** Passed — minimum-participant filter narrows visible slots as demonstrated in Sprint Review
**Executed by:** Vladislav Konovalov (demo); customer observed UAT segment
**Execution date:** 2026-07-05
**Evidence:** [Sprint Review summary](../reports/week5/sprint-review-summary.md); private recording (Moodle only)

### Preconditions

- A meeting has at least three participants with overlapping availability.
- The organizer opens the meeting heatmap on MVP v2.

### Steps

1. Open the meeting availability view.
2. Apply the minimum-participant filter.
3. Verify only slots meeting the threshold remain emphasized or visible according to the product design.
4. Change participant availability and verify the filtered view updates.

### Expected result

- The organizer can narrow the grid to slots with enough participant overlap.
- The filter helps scheduling decisions without requiring manual slot-by-slot inspection.

### Feedback

- Customer accepted the filter as useful but still requested clearer booking-state messaging elsewhere on the page.

### History

| Date | Version | Result | Notes |
|---|---|---|---|
| 2026-07-05 | 2.0 | Passed | Demonstrated during Sprint Review |
| — | 2.0 | Not executed | Initial scenario for MVP v2 |

---

## UAT-006 — Change or cancel a booked room

**Traceability:** US-007; [#139](https://github.com/one-zero-eight/monorepo/pull/139)
**Role:** Meeting organizer
**Status:** Active
**Result (Week 6):** Passed — changing, synchronizing, and canceling a booked room work as expected
**Executed by:** Lisitskii Nikita (demo)
**Execution date:** 2026-07-12
**Evidence:** [API contract](interface.md#change-booked-room); [automated contract tests](../../../tests/when2meet/test_events.py)

### Preconditions

- The organizer has a meeting with an exact selected time and a booked room.
- A second room is available for the complete selected meeting time.

### Steps

1. Open the meeting details and note the booked room.
2. Change the reservation to the second available room.
3. Reload the meeting and verify the new room remains selected.
4. Change the meeting title and selected time.
5. Verify the booked-room reservation reflects the new title and time.
6. Cancel the room reservation.
7. Reload the meeting details.

### Expected result

- Changing rooms creates the new reservation, cancels the previous reservation, and stores the new room on the meeting.
- Changing the meeting title or selected time updates the existing room reservation.
- The selected meeting time cannot be cleared while a room is booked.
- Canceling removes the external reservation and clears the booked room from the meeting.
- Deleting a meeting with a booked room also cancels its room reservation.
- Only the meeting organizer can book, change, or cancel a room.

### History

| Date | Version | Result | Notes |
|---|---|---|---|
| 2026-07-12 | Trial release | Passed | Booking change, synchronization, cancellation, and cleanup verified during demo |
