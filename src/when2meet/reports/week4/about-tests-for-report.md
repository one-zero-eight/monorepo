
## Automated Testing

When2Meet automated tests are stored in the normal repository location for this Python/FastAPI stack:

- `tests/when2meet/test_event_schemas.py`
- `tests/when2meet/test_events.py`
- `tests/when2meet/test_when2meet_startup.py`

Testing strategy, commands, critical modules, evidence distinctions, and coverage targets are documented in `src/when2meet/docs/testing.md`.

## Critical Module Coverage

Latest local evidence command:

```bash
uv run -m pytest tests/when2meet --cov=src/when2meet --cov-report=term-missing
```

Result: 29 When2Meet tests passed.

| Module | Coverage | Requirement |
|---|---:|---:|
| `src/when2meet/modules/events/routes.py` | 95% | 30% |
| `src/when2meet/modules/events/events_repo.py` | 98% | 30% |
| `src/when2meet/modules/events/schemas.py` | 99% | 30% |

Global monorepo coverage may be lower when running only `tests/when2meet` because the repository contains multiple product services outside the When2Meet scope.

## Additional QA Options Considered

Available additional automated QA checks considered:

- OpenAPI contract drift check for the When2Meet FastAPI schema.
- Dependency vulnerability audit for Python dependencies.
- Secret scanning for accidental committed credentials.
- License compliance scan for dependency licensing risk.
- Container/image security scan for deployable service images.

Link checking, including Lychee, was not considered eligible for Assignment 4 additional QA evidence because the assignment explicitly excludes link-checking jobs.

## Selected Additional QA Check

The selected additional QA check is the When2Meet OpenAPI contract drift check.

It compares the committed contract in `src/when2meet/api/openapi.yaml` with the schema generated from the current FastAPI app. The check fails if the backend API changes without updating the committed contract.

## QA Objective

The objective is to prevent API contract drift between the backend implementation and the documented OpenAPI contract used by frontend and integration consumers.

This risk matters because When2Meet depends on API consumers sending event, slot, and participant data in the expected shape. A stale API contract can cause broken clients, incorrect integration assumptions, or hidden release regressions even when backend unit and integration tests pass.

## CI Location

The additional QA check runs in CI in:

- `.github/workflows/when2meet-qa.yaml`

The workflow job is:

- `OpenAPI contract drift`

Required tests and coverage evidence run through the existing pytest workflow:

- `.github/workflows/tests.yaml`

## Evidence Distinctions

Pytest output is unit/integration test evidence.

Coverage output is critical-module coverage evidence.

The OpenAPI contract drift workflow is the Assignment 4 additional QA check evidence.

Lychee and other link checkers are link-checking evidence only and do not satisfy the Assignment 4 additional QA requirement.

QRT evidence is separate from automated tests, coverage, linting, formatting, type checking, build checks, link checking, and the OpenAPI contract drift check unless the process requirements explicitly allow a specific artifact as QRT evidence.

## Limitations and Deferred QA Work

The selected QA check protects API contract consistency, but it does not prove end-to-end frontend compatibility. Future QA work should add browser-level or deployed-environment checks once the frontend integration surface is stable.

Dependency vulnerability auditing and secret scanning remain useful future additions, but they were not selected as the Assignment 4 additional QA check for this iteration.
