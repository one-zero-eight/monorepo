# Week 2 Analysis

## Learning points

- **User stories:** Stable IDs US-001–US-010 give a single backlog the team and customer can reference; separating organizer (US-001, US-002, US-007, US-008, US-010) from participant (US-003, US-004, US-006, US-009) flows clarified MVP v1 boundaries.
- **Prioritization:** Four Must Have stories (US-001, US-002, US-003, US-006) form a minimal schedulable product; Should/Could stories (calendar, room booking, reminders, edit/cancel) stay visible without blocking the first release.
- **Prototyping:** Customer review showed that a partial polished Figma mock is weaker than a complete low-fidelity page map — missing place selection and response search were called out explicitly.
- **Interface design:** Primary external interface for users is the mobile web UI (Figma + hosted frontend); the REST API is the supporting interface prototype for data flows.
- **MVP v0 split:** Frontend and API are both deployed (pre frontend + hosted Swagger); local setup remains for development.
- **Customer validation:** Open meetings and link passwords were rejected quickly; heat-map / aggregated responses and calendar-day selection were confirmed.

## Validated assumptions

| Assumption | Outcome |
| --- | --- |
| Mobile-first UI is appropriate | **Confirmed** — prototype targets phones. |
| Password on shared links is needed | **Rejected** — InnoHassle identity + host participant management. |
| Public open-meetings discovery is in scope | **Rejected** — invited scheduling only. |
| Heat map / aggregated responses help pick a time | **Confirmed** — US-006 aligns with customer-approved results view. |
| Calendar integration is desired | **Confirmed** — US-004; deferred past MVP v1. |
| Room booking after best time is desired | **Confirmed** — US-007; deferred past MVP v1. |
| Notifications are ready in InnoHassle | **Rejected** — US-008/US-009 stay Could Have. |
| FastAPI + MongoDB models events and availability | **Confirmed** — local API smoke check and tests pass. |
| MIT public monorepo is acceptable to customer | **Confirmed** — development in [one-zero-eight/monorepo](https://github.com/one-zero-eight/monorepo). |
| InnoHassle design system should be reused | **Confirmed** in meeting. |

## Needs clarification

- Exact calendar API for US-004 (read busy times vs export only).
- Room-booking UX: book at creation vs after consensus (US-007).
- When to deploy backend API alongside hosted frontend.
- Public view-only Postman workspace link (collection exists in repo only).
- Protected default-branch screenshot for README (if not yet captured).

## Planned response

| Gap | Action | Artifacts |
| --- | --- | --- |
| Incomplete Figma | Add place selection, response search, participant list screens | [Figma](https://www.figma.com/design/Q31P4ba6YlmTOzoXC3W3E7/Untitled?node-id=0-1&t=8UaoXVNW08qHuwuY-1), [customer-meeting-summary.md](customer-meeting-summary.md) |
| MVP v1 delivery | Implement US-001–US-003, US-006 with InnoHassle auth | [user-stories.md](user-stories.md) |
| Backend deployment | Done — [hosted Swagger](https://api.innohassle.ru/when2meet/v0/docs) linked from README | [mvp-v0-report.md](mvp-v0-report.md) |
| Integrations | Spike with one-zero-eight for calendar and room booking | US-004, US-007 |
| Reminders | Wait for InnoHassle notification infrastructure | US-008, US-009 |
| API conventions | Align with monorepo services after tech-team review | [api/openapi.yaml](../../api/openapi.yaml) |
