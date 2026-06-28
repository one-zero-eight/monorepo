# Customer Review Summary

**Date:** 2026-06-27

**Participants / roles:**

- Customer (stakeholder)
- Tester / team representative
- Developer (Sprint increment demo)
- Observer (QA / documentation)

> Recording, exact timecodes, and identifying details are submitted privately through Moodle. This public summary is sanitized.

**Sprint Goal reviewed:**

Deliver functional event creation with varied time-selection modes, reliable link sharing, and initial room booking capabilities.

**Delivered increment discussed:**

- Event creation with corrected calendar date selection.
- Two event creation modes: fixed daily timeframe and administrator-preselected slots.
- Optional description field restored.
- Link sharing with short slugs instead of long UUIDs.
- Email and Telegram profile data transfer; SSO redirects working.
- Meeting deletion and **My meetings** tab for owned past meetings.
- Calendar export from the application to the user's calendar.

**UAT results (sanitized):**

| Scenario | Result | Notes |
|---|---|---|
| Participant search on meeting grid | Passed | Search worked without issues |
| Room booking | Partial | Modal and room list work; explicit reservation time not confirmed |
| Reverse calendar overlay (UAT-001) | Not executed | Feature not in this increment |

**Quality evidence discussed:**

- Previously reported calendar date-selection defect fixed.
- A temporary rollback was required when a login-loop regression appeared during development.

**Feedback (high level):**

- UI slot selection is awkward; visual design needs improvement.
- Participants without explicit time selection must not count as having answered.
- Minimum-participant intersection filter is not user-friendly.

**Approvals or requested changes:**

- **Approved:** link sharing, short slugs, SSO redirects, deletion.
- **Approved:** past owned meetings may disappear instead of using a separate archive tab.
- **Requested:** reverse calendar overlay during slot selection (optional).
- **Requested:** room booking must ask for explicit time; handle multiple/zero intersections.
- **Requested:** colorblind-friendly single control for maximum intersection.
- **Requested:** click a slot to see which participants selected it.

**Risks:**

- Data migration when organizer edits slots after replies exist.
- Heatmap reliance on purple gradients is not colorblind-safe.
- Room booking edge cases (no overlap, multiple overlaps).

**Action points → backlog:** [#92](https://github.com/one-zero-eight/monorepo/issues/92)–[#100](https://github.com/one-zero-eight/monorepo/issues/100) (see [customer-feedback-issues.md](customer-feedback-issues.md)).
