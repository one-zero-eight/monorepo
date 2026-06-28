# User Acceptance Tests

Maintained end-user-facing acceptance scenarios for When2Meet. Execution results for Assignment 4 (Sprint 2) are recorded below without private customer-identifying details.

## UAT-001 — Choose a meeting time with calendar-event awareness

**Traceability:** US-004  
**Role:** Meeting participant  
**Status:** Active  
**Result (Week 4):** Not executed — reverse calendar overlay not implemented in this increment  
**Executed by:** —  
**Execution date:** 2026-06-27 (Sprint Review session; scenario deferred)  
**Evidence:** Customer UAT recording (Moodle submission only)

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
| 2026-06-27 | 1.0 | Not executed | Reverse calendar integration deferred to backlog |
| — | 1.0 | Not executed | Initial scenario |

---

## UAT-002 — Find a participant, review availability, and remove them from a meeting

**Traceability:** US-012; US-013  
**Role:** Meeting organizer  
**Status:** Active  
**Result (Week 4):** Passed (participant search); removal flow not exercised in recorded session  
**Executed by:** Customer (observer: team tester)  
**Execution date:** 2026-06-27  
**Evidence:** Customer UAT recording (Moodle submission only)

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
| 2026-06-27 | 1.0 | Passed (search) | Removal steps not run in recorded UAT |
| — | 1.0 | Not executed | Initial scenario |

---

## UAT-003 — Book an available room for a selected meeting time

**Traceability:** US-007  
**Role:** Meeting organizer  
**Status:** Active  
**Result (Week 4):** Partial — modal and room list work; explicit booking time not confirmed  
**Executed by:** Customer  
**Execution date:** 2026-06-27  
**Evidence:** Customer UAT recording (Moodle submission only)

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
| 2026-06-27 | 1.0 | Partial | Room modal works; time-selection logic incomplete |
| — | 1.0 | Not executed | Initial scenario |
