# Customer feedback — GitHub issues

Issues created from Sprint 2 customer feedback (Assignment 4). Each issue notes **Source: customer feedback** in the description.

| Issue | Title |
|---|---|
| [#92](https://github.com/one-zero-eight/monorepo/issues/92) | Show personal calendar events on the availability selection grid (optional) |
| [#93](https://github.com/one-zero-eight/monorepo/issues/93) | Room booking flow: explicit time selection and intersection edge cases |
| [#94](https://github.com/one-zero-eight/monorepo/issues/94) | Single-button control to highlight maximum availability intersection (accessibility) |
| [#95](https://github.com/one-zero-eight/monorepo/issues/95) | Time-slot detail view listing participants available at that slot |
| [#96](https://github.com/one-zero-eight/monorepo/issues/96) | Participant list entry without selected slots must not count as availability |
| [#97](https://github.com/one-zero-eight/monorepo/issues/97) | API support for editing participant availability replies |
| [#98](https://github.com/one-zero-eight/monorepo/issues/98) | Define behaviour when organizer changes slots after participants already replied |
| [#99](https://github.com/one-zero-eight/monorepo/issues/99) | Redesign availability grid interaction and visual design |
| [#100](https://github.com/one-zero-eight/monorepo/issues/100) | Simplify intersection filter UX (follow-up to accessibility control) |

---

## Issue A — Reverse calendar overlay on availability grid

**GitHub:** [#92](https://github.com/one-zero-eight/monorepo/issues/92)

**Title:** Show personal calendar events on the availability selection grid (optional)

**Labels:** `enhancement`, `customer-feedback`

**Description:**

```markdown
## Source
Customer feedback from Sprint Review / UAT on 2026-06-27.

## Problem
Export from When2Meet to the user's calendar works, but participants cannot see their existing weekly schedule while selecting availability slots. The customer needs optional reverse integration so overlaps are visible during slot selection.

## Acceptance criteria
- Given a participant with linked calendar data, when they open the availability grid, then their existing events for the meeting date range are visible on relevant slots.
- Given the overlay is visible, when the participant toggles "Hide calendar events", then calendar markings are hidden.
- Given a slot overlaps a calendar event, when the participant selects it, then the UI clearly indicates the conflict while still allowing selection if permitted by product rules.
```

---

## Issue B — Room booking must ask for explicit reservation time

**GitHub:** [#93](https://github.com/one-zero-eight/monorepo/issues/93)

**Title:** Room booking flow: explicit time selection and intersection edge cases

**Labels:** `bug`, `customer-feedback`

**Description:**

```markdown
## Source
Customer feedback from customer-executed UAT on 2026-06-27.

## Problem
The room booking modal lists available rooms but does not clearly ask which time to reserve. The customer asked what happens when there are several time intersections or none at all.

## Acceptance criteria
- Given a meeting with one clear intersection, when the organizer opens room booking, then the proposed reservation time is shown and confirmable.
- Given multiple intersections, when the organizer books a room, then they must choose which intersection time to use before confirmation.
- Given zero intersections, when the organizer opens room booking, then the UI explains that booking is not possible and does not silently pick a time.
- Given a confirmed booking, when the organizer returns to meeting details, then the booked room and time are shown consistently.
```

---

## Issue C — Colorblind-friendly control for maximum participant intersection

**GitHub:** [#94](https://github.com/one-zero-eight/monorepo/issues/94)

**Title:** Single-button control to highlight maximum availability intersection (accessibility)

**Labels:** `enhancement`, `accessibility`, `customer-feedback`

**Description:**

```markdown
## Source
Customer feedback from Sprint Review on 2026-06-27.

## Problem
The heatmap relies on purple shade gradients. Colorblind users cannot distinguish intersections reliably. The customer requested one clear control instead of the current minimum-participant filter.

## Acceptance criteria
- Given a meeting with participant availability, when the organizer activates "Show best intersection" (or equivalent single control), then the slot(s) with the maximum intersection count are highlighted without relying only on color shade.
- Given the control is active, when availability changes, then the highlighted intersection updates.
- Given a colorblind-safe mode, when enabled, then intersection information remains understandable without distinguishing purple gradients alone.
```

---

## Issue D — Show participant names when clicking a time slot

**GitHub:** [#95](https://github.com/one-zero-eight/monorepo/issues/95)

**Title:** Time-slot detail view listing participants available at that slot

**Labels:** `enhancement`, `customer-feedback`

**Description:**

```markdown
## Source
Customer feedback from Sprint Review on 2026-06-27.

## Problem
Organizers cannot see who confirmed availability for a specific slot without cumbersome filtering.

## Acceptance criteria
- Given a meeting grid with availability, when the organizer clicks a time slot, then a detail view lists participant names (or identifiers) who selected that slot.
- Given no participants selected the slot, when the organizer clicks it, then the UI states that no one is available at that time.
```

---

## Issue E — Do not count participants without explicit time selection

**GitHub:** [#96](https://github.com/one-zero-eight/monorepo/issues/96)

**Title:** Participant list entry without selected slots must not count as availability

**Labels:** `bug`, `customer-feedback`

**Description:**

```markdown
## Source
Customer feedback from Sprint Review on 2026-06-27.

## Problem
If a user appears in the participant list but has not explicitly selected a time, the system must not treat that as a valid answer for heatmap or intersection logic.

## Acceptance criteria
- Given a participant joined but selected no slots, when the heatmap or intersection is calculated, then that participant does not increase intersection counts.
- Given a participant later selects slots, when the heatmap refreshes, then only explicit selections are counted.
```

---

## Issue F — Backend endpoint for editing participant replies

**GitHub:** [#97](https://github.com/one-zero-eight/monorepo/issues/97)

**Title:** API support for editing participant availability replies

**Labels:** `enhancement`, `customer-feedback`, `backend`

**Description:**

```markdown
## Source
Customer feedback from Sprint Review on 2026-06-27.

## Problem
Participants cannot edit their replies because the backend endpoint is missing. Frontend work is blocked until the API exists.

## Acceptance criteria
- Given an authenticated participant with an existing reply, when they submit an update, then availability is updated and persisted.
- Given invalid slot selections, when the participant updates, then the API returns a clear validation error.
- Coordinate with the monorepo backend team if the endpoint lives outside `src/when2meet`.
```

---

## Issue G — Data migration when organizer edits meeting slots

**GitHub:** [#98](https://github.com/one-zero-eight/monorepo/issues/98)

**Title:** Define behaviour when organizer changes slots after participants already replied

**Labels:** `spike`, `customer-feedback`

**Description:**

```markdown
## Source
Customer feedback from Sprint Review on 2026-06-27.

## Problem
It is unclear how to migrate participant replies when an administrator changes the meeting slot grid after selections exist.

## Acceptance criteria
- Document the chosen policy (preserve valid intersections, drop invalid slots, notify participants, etc.).
- Implement server-side normalization so participant availability never references slots outside the current grid.
- Add tests for the migration/normalization rules.
```

---

## Issue H — UI/UX redesign for slot selection and visual polish

**GitHub:** [#99](https://github.com/one-zero-eight/monorepo/issues/99)

**Title:** Redesign availability grid interaction and visual design

**Labels:** `enhancement`, `customer-feedback`, `ui-ux`

**Description:**

```markdown
## Source
Customer feedback from Sprint Review on 2026-06-27.

## Problem
The customer described the current UI as awkward: slot self-selection is inconvenient and several elements look visually unappealing. Approved features (link sharing, SSO, deletion) work, but the scheduling interaction needs a dedicated redesign phase.

## Acceptance criteria
- Produce updated design guidance aligned with customer expectations.
- Improve slot self-selection interaction on mobile and desktop widths used in production.
- Verify changes with customer review before closing.
```

---

## Issue I — Replace minimum-participant filter with simpler intersection control

**GitHub:** [#100](https://github.com/one-zero-eight/monorepo/issues/100)

**Title:** Simplify intersection filter UX (follow-up to accessibility control)

**Labels:** `enhancement`, `customer-feedback`

**Description:**

```markdown
## Source
Customer feedback from Sprint Review on 2026-06-27.

## Problem
The minimum-number-of-participants filter added in the Sprint is hard to use. The customer prefers a single obvious control that surfaces intersection data immediately.

## Acceptance criteria
- Remove or supersede the confusing minimum-participant filter pattern.
- Provide one primary control that shows intersection information without multi-step filtering.
- May be implemented together with [#94](https://github.com/one-zero-eight/monorepo/issues/94); keep traceability in the issue body.
```

---

## Deferred / already addressed in Sprint 2

| Feedback | Sprint 2 response | Backlog issue |
|---|---|---|
| Link sharing with short slugs | Delivered and approved | — |
| SSO redirects | Delivered and approved | — |
| Meeting deletion | Delivered and approved | — |
| Past meetings should disappear (no archive tab) | Accepted; current behaviour kept | — |
| Calendar export (app → user calendar) | Delivered | Reverse overlay → [#92](https://github.com/one-zero-eight/monorepo/issues/92) |
