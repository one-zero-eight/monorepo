## Learning points

- Follow-up maintenance is most effective when frontend behavior, backend contracts, and acceptance criteria are reviewed together. During Sprint 5, miscommunication between frontend developers led to different interpretations of the intended mobile interaction and heatmap presentation.
- When a requirement or interaction is unclear, asking the customer for clarification early is more effective than relying on internal assumptions. A short confirmation using a concrete scenario or prototype can prevent rework and align the team on the expected outcome.
- Final transition work is part of the product delivery, not only an administrative activity. The maintained [customer handover](../../docs/customer-handover.md), [Week 7 report](README.md), UAT evidence, and recovery guidance make the final MVP usable and reviewable after the course. We managed to transfer the product to the customer without any problems.
- The final Sprint Review demonstrated the value of separating release-critical functionality from optional polish. The customer approved MVP v3 while clearly identifying mobile viewport behavior, slot-selection discoverability, and legend placement as post-course improvements ([Sprint Review summary](sprint-review-summary.md)).

## Validated assumptions

- The hosted MVP v3 supports the agreed end-to-end scheduling flow: meeting creation and sharing, participant availability collection, heatmap review, final-time selection, and optional room booking.
- Requiring an explicit timezone offset for the selected meeting time provides a reliable contract for available-room lookup and booking without backend timezone inference ([#152](https://github.com/one-zero-eight/monorepo/pull/152)).
- Existing tests, QRTs, CI checks, and maintained documentation can remain active through final maintenance and provide credible release evidence rather than serving only as earlier-assignment artifacts.
- Customer review is useful not only for acceptance but also for distinguishing functional gaps from lower-priority usability improvements.

## Friction and gaps

- Frontend coordination was not sufficiently explicit. Team members held different assumptions about mobile scrolling, slot-selection behavior, and where explanatory information should appear.
- The mobile flow can still move the selected slot or its result outside the active viewport, reducing context for the user.
- Double-click-and-drag selection is not sufficiently discoverable, especially on touch devices.
- The heatmap legend and color explanation require more prominent placement and clearer wording on both desktop and mobile.
- Full customer-side operation was outside the reached handover scope because deployment access, runtime secrets, monitoring, rollback authority, and production ownership remain with Team 108 / InNoHassle maintainers.

## Planned response

- **Team communication:** Record a shared interaction contract for frontend work, including the expected user action, resulting state, responsive behavior, and acceptance examples before implementation begins.
- **Customer clarification:** When requirements are ambiguous, present the customer with a concrete scenario, mockup, or prototype and record the confirmed decision in the relevant issue and acceptance criteria.
- **Product usability:** Treat viewport-local feedback, a simpler touch-friendly slot-selection interaction, and an unambiguous legend above the heatmap as post-course improvement candidates.
- **Quality:** Continue using task-based desktop and mobile checks alongside automated tests so interaction problems are identified before a customer review.
- **Transition:** Keep the [customer handover](../../docs/customer-handover.md), [roadmap](../../docs/roadmap.md), and operational limitations current if deployment ownership or support responsibilities change.
