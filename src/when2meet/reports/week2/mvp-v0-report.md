# MVP v0 Report

## Purpose

When2Meet MVP v0 establishes a runnable product foundation for the course:

1. **Backend (API):** FastAPI service with MongoDB persistence for events and participant availability — modular Tier 3 layout in the [one-zero-eight/monorepo](https://github.com/one-zero-eight/monorepo).
2. **Frontend (prototype):** Mobile-oriented UI deployed for smoke checks and customer review.

MVP v0 does not implement every user story end-to-end; it proves the technical base and demonstrates the proposed MVP v1 experience.

## Deployment URL or runnable artifact

| Component | URL | Status |
| --- | --- | --- |
| **Frontend (hosted)** | [https://pre.innohassle.ru/when-to-meet](https://pre.innohassle.ru/when-to-meet) | Deployed — primary TA access point for UI smoke check |
| **API (hosted)** | [https://api.innohassle.ru/when2meet/v0](https://api.innohassle.ru/when2meet/v0) | Deployed backend |
| **Swagger UI (hosted)** | [https://api.innohassle.ru/when2meet/v0/docs](https://api.innohassle.ru/when2meet/v0/docs) | Primary TA access point for API smoke check |
| **Backend API (local)** | `http://localhost:8020` | Optional local development |
| **API base path** | `/api/v0` (local) / `/when2meet/v0` (hosted) | |
| **Swagger UI (local)** | `http://localhost:8020/docs` | When running backend locally |

## Public video demonstration

[Yandex Disk — MVP v0 demo (< 2 min)](https://disk.yandex.ru/i/NtGKNllihRGJ4Q)

Shows the hosted frontend and/or local API smoke check (sanitized, no credentials).

## Local setup

Documented in the [root README](../../../../README.md#development). Summary:

1. Start MongoDB: `docker compose up --wait`
2. Configure `settings.yaml` with `when2meet_service.app_root_path: "/api/v0"`
3. Run backend: `uv run -m src.when2meet --reload`
4. Run tests: `uv run pytest tests/when2meet/`

## Smoke check

### A. Hosted frontend (primary for TA)

1. Open [https://pre.innohassle.ru/when-to-meet](https://pre.innohassle.ru/when-to-meet).
2. **Expected:** Application loads; primary navigation between prototype screens works.
3. **Expected:** At least one interactive flow is demonstrable (e.g. meeting creation UI, time selection, or results view depending on current build).

### B. Hosted API (primary for TA)

1. Open [https://api.innohassle.ru/when2meet/v0/docs](https://api.innohassle.ru/when2meet/v0/docs).
2. **Expected:** Swagger UI loads with event endpoints.
3. Execute (or verify in demo video):
   - `POST /events/` — create a meeting with slots (**US-001**).
   - `PUT /events/{id}/participants` — submit availability (**US-003**).
   - `GET /events/{id}` — read aggregated data for heat map (**US-006**).

### C. Local API (optional)

1. Start the service locally (see [Local setup](#local-setup)).
2. Open `http://localhost:8020/docs`.
3. **Expected:** Swagger UI loads with `/api/v0` endpoints.
4. Same steps as hosted smoke check under `/api/v0`.

## Relationship to the prototype and proposed MVP v1 stories

| Story | MVP v0 coverage |
| --- | --- |
| **US-001** Create meeting | API: `POST /events/`; Figma + hosted frontend |
| **US-002** Share meeting | Figma / frontend link flow; no dedicated share API yet |
| **US-003** Join via link, submit times | API: `PUT /events/{id}/participants`; frontend prototype |
| **US-006** Heat map of opinions | API returns participant data; heat-map UI in prototype / hosted frontend |
| **US-004** Calendar awareness | Not implemented |
| **US-007** Room booking | Not implemented |
| **US-008–US-009** Reminders | Not implemented |
| **US-010** Edit/cancel meeting | Not implemented |
| **US-005** MEOW button | Excluded (Won't Have) |

Initial proposed MVP v1 scope: **US-001**, **US-002**, **US-003**, **US-006** — see [user-stories.md](user-stories.md).

## Implemented features

- Modular Tier 3 backend (`modules/events`).
- MongoDB persistence via Beanie ODM.
- API versioning under `/api/v0`.
- Slot validation for participant availability.
- Swagger UI with search filters.
- Automated tests for events module.
- Frontend and API deployed to InnoHassle pre/production infrastructure.

## Current limitations

- **Authentication:** participant identified by name in v0; InnoHassle SSO planned for MVP v1.
- **Integrations:** calendar, maps, room booking, notifications not connected.
- **Prototype gaps:** meeting place screen, response search (customer feedback).
