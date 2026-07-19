## What went well

- Sprint 5 completed the final MVP v3 delivery and the customer confirmed that the product is functionally complete, ready for release, and handed over to Team 108 ([Sprint Review summary](sprint-review-summary.md)).
- Mobile scrolling and slot selection were improved, while selected-time timezone handling was completed and verified through [UAT-003](../../docs/user-acceptance-tests.md#uat-003--book-an-available-room-for-a-selected-meeting-time).
- The final documentation package covers the roadmap, UAT, testing, architecture, recovery, and the actual [customer handover](../../docs/customer-handover.md) boundaries.
- More team members attended the final customer session than in previous Sprints, and the review produced explicit acceptance and support expectations.

## What did not go well

- The exact mobile interaction path was still not sufficiently validated before the review: selecting a slot could force the customer to scroll and lose the context of the selected cell.
- Double-click-and-drag slot selection remained difficult to discover and inconvenient on touch devices.
- The heatmap legend and color explanation were still not prominent enough; the customer again requested clear labels above the grid on both desktop and mobile ([UAT-004](../../docs/user-acceptance-tests.md#uat-004--distinguish-my-selected-slots-on-the-availability-grid)).
- Some Week 6 UI feedback was improved but not fully resolved before the final demonstration, so minor UX work moved outside the course scope.

## What the team changed or attempted to change based on the previous Sprint Retrospective, and what results they observed

- The previous retrospective required a smoke test of the exact demo path on mobile and desktop. The team improved and demonstrated mobile scrolling and selection, but the customer still reproduced a viewport-context problem. The change helped, but the validation scenario was not strict enough to confirm that results remain visible after every slot interaction.
- The team kept customer-facing documentation as a first-class deliverable and maintained written transition evidence. This worked: the customer approved the release and confirmed handover to Team 108, while the final [handover document](../../docs/customer-handover.md) records the remaining operational boundaries.
- The team continued converting review feedback into traceable work through [#146](https://github.com/one-zero-eight/monorepo/issues/146) and [#149](https://github.com/one-zero-eight/monorepo/issues/149). The core course scope closed successfully, but legend placement and selection UX remain post-course improvements.

## Action points

1. **Run a short task-based mobile and desktop usability check before the next release:** verify that selecting a slot keeps the selected cell, result, and legend visible without extra scrolling, and record the result against the relevant PBI.
2. **Prototype and customer-test one simpler slot-selection interaction:** replace double-click-and-drag with a touch-friendly approach and place an unambiguous legend above the heatmap before implementation is considered complete.
