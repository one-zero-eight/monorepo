# User Acceptance Tests

Maintained end-user-facing acceptance scenarios for When2Meet. Execution results for Assignment 4 (Sprint 2) are recorded below without private customer-identifying details.

## UAT-001 — Choose a meeting time with calendar-event awareness

**Traceability:** US-004
**Role:** Meeting participant
**Status:** Active
**Result (Week 4):** Not executed — reverse calendar overlay not implemented in this increment
**Result (Week 5):** Passed with change request — overlay works on desktop and mobile; customer requested hide-calendar toggle
**Executed by:** Vladislav Konovalov (demo); customer observed UAT segment
**Execution date:** 2026-07-05
**Evidence:** [Sprint Review transcript](https://github.com/one-zero-eight/monorepo/blob/main/src/when2meet/reports/week5/sprint-review-transcript.md); private recording (Moodle only)

### Preconditions

- A test participant has an existing calendar event on Tuesday from 10:00 to 11:00.
- The participant has received a meeting invitation with an availability grid that includes Tuesday from 09:00 to 12:00.

### Steps

1. Open the meeting invitation.
2. View the availability grid.
3. Verify that the existing calendar event is marked at Tuesday 10:00–11:00.
4. Select **Hide calendar events**.
5. Verify that calendar-event markings are hidden.
6. Select availability for a time slot that overlaps the calendar event.
7. View the meeting heatmap or availability summary.

### Expected result

- Calendar events are visible on their relevant time slots when the grid opens.
- The participant can hide calendar events using the provided control.
- Selecting a conflicting time remains possible, but the system clearly indicates that it conflicts with the participant's calendar event.

### Feedback

- Customer requested reverse calendar integration during Sprint Review; export to external calendar works, import overlay does not → [#92](https://github.com/one-zero-eight/monorepo/issues/92).

### History

| Date | Version | Result | Notes |
|---|---|---|---|
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

**Traceability:** US-007
**Role:** Meeting organizer
**Status:** Active
**Result (Week 4):** Partial — modal and room list work; explicit booking time not confirmed
**Result (Week 5):** Partial — free-room selection works; booking state, optional flow, calendar link, and participant calendar push incomplete
**Executed by:** Vladislav Konovalov (demo); customer observed UAT segment
**Execution date:** 2026-07-05
**Evidence:** [Sprint Review transcript](https://github.com/one-zero-eight/monorepo/blob/main/src/when2meet/reports/week5/sprint-review-transcript.md); private recording (Moodle only)

### Preconditions

- A meeting has participant availability on the grid.
- At least one room is available in the test environment.

### Steps

1. Open the meeting details.
2. Select **Book a room**.
3. Review the list of available rooms.
4. Select one available room and confirm.

### Expected result

- The organizer sees rooms available for the selected meeting time.
- The system asks which specific time to book when multiple or zero intersections exist.
- The meeting details show the booked room with the correct date and time.

### Feedback

- Customer asked which reservation time is used; team acknowledged the flow must ask explicitly and handle multiple/zero intersection edge cases → [#93](https://github.com/one-zero-eight/monorepo/issues/93).

### History

| Date | Version | Result | Notes |
|---|---|---|---|
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
