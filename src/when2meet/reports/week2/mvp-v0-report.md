# MVP v0 Report

## Purpose

A professional FastAPI-based backend foundation for the When2Meet service, following the "Normal" (Tier 3) modular architecture of the monorepo. It provides core functionality for event creation and participant availability management with MongoDB persistence.

## Deployment URL or runnable artifact

- Local development: `http://localhost:8020`
- API Base Path: `/api/v0`
- Swagger UI: `http://localhost:8020/docs`

## Local setup

Run from the monorepo root:

1. **Start infrastructure** (MongoDB):
   ```bash
   docker compose up --wait
   ```

2. **Prepare settings**:
   Ensure `settings.yaml` exists in the root (copied from `settings.example.yaml`) and includes:
   ```yaml
   when2meet_service:
     app_root_path: "/api/v0"
   ```

3. **Run the service**:
   ```bash
   uv run -m src.when2meet --reload
   ```

4. **Run tests**:
   ```bash
   uv run pytest tests/when2meet/
   ```

## Smoke check
1. Open `http://localhost:8020/docs`.
2. Expected result: Swagger UI loads with endpoints available via the `/api/v0` server.
3. Validate Features:
   - Use `POST /api/v0/events` to create a meeting.
   - Use `PUT /api/v0/events/{id}/participants` to submit availability.
   - Use `GET /api/v0/events/{id}` to see aggregated results.

## Relationship to the prototype and proposed MVP v1 stories

MVP v0 implements the technical foundation for the following proposed stories:
- **US-01** (Creation of meetings): Backend logic and storage are ready.
- **US-02** (Providing availability): Implemented via the participants endpoint.
- **US-03** (Viewing results): Aggregated data is returned in the event details.

## Implemented Features

- **Modular Tier 3 Architecture**: Logic separated into modules (`events`).
- **Data Persistence**: Fully integrated with MongoDB using Beanie ODM.
- **API Versioning**: Standardized `/api/v0` prefix managed via `root_path`.
- **Validation**: Strict validation for participant time slots against event slots.
- **Swagger UI Enhancement**: Added search filters and professional descriptions.
- **Automated Testing**: 100% coverage for core business logic in the `events` module.

## Current Limitations

- **Authentication**: Not implemented in v0; all users are identified by name only.
- **Advanced Conflicts**: Simple update logic for participants; no complex merge resolution.
- **Front-end**: This is a pure backend MVP v0.
