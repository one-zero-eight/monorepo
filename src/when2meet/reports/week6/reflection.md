## Learning points

- Separating final meeting-time selection from room booking made the organizer flow understandable; combining them in one control was the main Sprint 3 confusion.
- A trial release is only as strong as the customer-facing docs: README and `docs/customer-handover.md` review prevented last-minute handover surprises.
- Live room-booking demos depend on an external service; contract tests and a second verification pass were required when the booking service was temporarily down.
- Small UX gaps (legend placement, inability to clear a selected time) surface immediately in a customer trial even when core acceptance tests pass.

## Validated assumptions

- The hosted pre-production deployment on Team 108 is sufficient for independent customer trial use with InNoHassle SSO.
- Maintaining UAT scenarios in `docs/user-acceptance-tests.md` and executing them with the customer produces clearer acceptance than informal walkthroughs.
- Customer acceptance of README and customer-handover content is a useful gate before claiming transition readiness.

## Friction and gaps

- Heatmap legend was delivered at the bottom; customer asked to move it to the top.
- Selected final meeting time could not be cleared during the demo — a bug queued for Sprint 5.
- Mobile validation remains a customer condition for final release.
- Room-booking service unavailability briefly blocked live end-to-end demonstration.

## Planned response

- **Product:** Sprint 5 — legend top placement, selected-time clear, mobile validation, remaining polish from [#146](https://github.com/one-zero-eight/monorepo/issues/146).
- **Transition:** Keep handover docs current; confirm final handover level and customer-confirmation status in Week 7.
- **Quality:** Keep pytest, QRTs, secret scan, and UAT evidence aligned with MVP v3.
