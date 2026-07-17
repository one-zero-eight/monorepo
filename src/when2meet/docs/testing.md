# When2Meet Testing

## Contents

- [Scope](#scope)
- [How to Run](#how-to-run)
- [Critical Modules](#critical-modules)
- [Unit Tests](#unit-tests)
- [Integration Tests](#integration-tests)
- [Additional QA Check](#additional-qa-check)
- [Automated Quality Requirement Tests](#automated-quality-requirement-tests)
- [Evidence Types](#evidence-types)
- [Sprint 5 Extension](#sprint-5-extension)
- [Maintenance](#maintenance)

## Scope

This document covers automated testing and QA checks for the When2Meet product code under `src/when2meet`.

Tests are stored in the normal repository test location for this stack: `tests/when2meet`.

## How to Run

Start the shared test infrastructure first:

```bash
docker compose -f docker-compose.test.yaml up --wait
```

Run the When2Meet tests:

```bash
uv run -m pytest tests/when2meet
```

Run When2Meet tests with coverage:

```bash
uv run -m pytest tests/when2meet --cov=src/when2meet --cov-report=term-missing
```

Run the additional QA check:

```bash
docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:latest dir --no-banner --redact --verbose /repo/src/when2meet
docker run --rm -v "$PWD:/repo" ghcr.io/gitleaks/gitleaks:latest dir --no-banner --redact --verbose /repo/tests/when2meet
```

## Critical Modules

| Module | Why it is critical | Coverage target | Current evidence |
|---|---|---:|---:|
| `src/when2meet/modules/events/routes.py` | Public meeting API, authorization checks, participant update rules, selected-time and room-booking contracts. | 30% line coverage | 100% |
| `src/when2meet/modules/events/events_repo.py` | Event persistence, slug lookup, participant upsert/removal, owner/participant queries. | 30% line coverage | 100% |
| `src/when2meet/modules/events/schemas.py` | Request/response contracts, timezone-aware datetime validation, and selected-time serialization. | 30% line coverage | 100% |

The current evidence comes from:

```bash
uv run -m pytest tests/when2meet --cov=src/when2meet --cov-report=term-missing
```

The repository-wide coverage percentage may be lower when only `tests/when2meet` is executed because the monorepo contains other product services that are not part of this product-scoped evidence.

## Unit Tests

Unit tests for critical product logic are in:

- `tests/when2meet/test_event_schemas.py`

They cover:

- event slot normalization without accepting timezone-less datetimes;
- deterministic sorting of event slots;
- participant availability validation;
- selected meeting time offset preservation;
- rejection of unknown request fields;
- `EventUpdate` keeps missing fields unset for PATCH payloads.

## Integration Tests

Integration tests are in:

- `tests/when2meet/test_events.py`
- `tests/when2meet/test_startup.py`
- `tests/when2meet/test_quality_requirements.py`

They cover important interactions between product components:

- FastAPI routes;
- authentication fixtures;
- mocked InNoHassle Accounts boundary;
- Beanie/MongoDB test infrastructure;
- event creation, retrieval, update, and deletion;
- participant availability updates and deletion;
- owner-only access control;
- not-found and invalid-request API contracts.
- selected meeting time persistence and owner-only updates.
- room availability, booking, change, cancellation, and cleanup through the Room Booking boundary.
- QA documentation, QRT, Definition of Done, and ADR traceability gates.

## Additional QA Check

The selected additional automated QA check is When2Meet secret scanning.

It scans only When2Meet product files for committed secrets:

- `src/when2meet`
- `tests/when2meet`

The check addresses the risk of accidentally committing API tokens, JWTs, private keys, service credentials, or other sensitive values in product code, tests, API artifacts, docs, and reports. That risk matters because When2Meet depends on authenticated InNoHassle Accounts identity data and API-backed scheduling flows.

The check runs in CI in:

- `.github/workflows/when2meet-qa.yaml`

It is intentionally distinct from:

- linting;
- formatting;
- type checking;
- build checks;
- unit tests;
- integration tests;
- coverage;
- automated QRTs;
- link checking, including Lychee.

Link checking remains useful repository QA, but it does not count as the Assignment 4 additional QA check.

## Automated Quality Requirement Tests

| QRT | Linked QR | Command or test | Latest result | Evidence |
|---|---|---|---|---|
| [QRT-001](quality-requirement-tests.md#qrt-001-critical-module-line-coverage) | QR-001 Testability | `pytest tests/when2meet --cov=src/when2meet --cov-report=xml:coverage.xml` | Passing with active coverage collection | [test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py) |
| [QRT-002](quality-requirement-tests.md#qrt-002-owner-only-event-mutation) | QR-002 Confidentiality | `pytest tests/when2meet/test_quality_requirements.py::test_qrt_non_owner_cannot_patch_or_delete_event` | Passing | [test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py) |
| [QRT-003](quality-requirement-tests.md#qrt-003-event-read-response-time) | QR-003 Time behaviour | `pytest tests/when2meet/test_quality_requirements.py::test_qrt_get_event_completes_within_time_budget` | Passing | [test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py) |
| [QRT-004](quality-requirement-tests.md#qrt-004-qa-documentation-and-architecture-traceability) | QR-004 Maintainability | `pytest tests/when2meet/test_quality_requirements.py::test_qrt_qa_documentation_keeps_gates_and_architecture_traceability` | Passing | [test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py) |

Quality requirement definitions: [quality-requirements.md](quality-requirements.md).

## Evidence Types

Pytest results are unit/integration test evidence.

Coverage reports are coverage evidence for critical modules.

The When2Meet secret scan workflow is additional QA check evidence.

QRT evidence is documented in [quality-requirement-tests.md](quality-requirement-tests.md) and implemented in `tests/when2meet/test_quality_requirements.py`. QRT evidence is kept separate from generic unit tests, coverage, lint, type, build, link-checking, and secret-scanning evidence unless process requirements explicitly allow a specific overlap.

## Sprint 5 Extension

Sprint 5 keeps the Assignment 4 testing, CI, coverage, quality-requirement-test, secret scan, and Definition of Done gates active.

The automated test suite now also checks maintained QA documentation itself. `QRT-004` verifies that:

- the required long-lived testing, quality-requirement, architecture traceability, QRT, and Definition of Done pages remain navigable with a table of contents;
- pytest, coverage, QRT, CI, and secret scan gates remain documented in both testing guidance and the Definition of Done;
- QR and QRT IDs stay linked both ways;
- accepted architecture decisions for repository boundaries, slug references, and InNoHassle Accounts integration remain referenced from QR/QRT evidence.
- the Week 7 final report exists, is linked from roadmap, handover, UAT, and root README, and preserves protected-default-branch CI evidence links.

Latest protected `main` evidence referenced by the Week 7 report:

| Check | Result | Link |
|---|---|---|
| Run tests | Success | [GitHub Actions run 29437789987](https://github.com/one-zero-eight/monorepo/actions/runs/29437789987) |
| When2Meet QA secret scan | Success | [GitHub Actions run 29437795124](https://github.com/one-zero-eight/monorepo/actions/runs/29437795124) |
| Links | Success | [GitHub Actions run 29437790384](https://github.com/one-zero-eight/monorepo/actions/runs/29437790384) |

## Maintenance

Tests added for Assignment 4 are maintained product assets. Later When2Meet changes must keep them passing or replace them with documented equivalent or stronger coverage when the product behavior changes.
