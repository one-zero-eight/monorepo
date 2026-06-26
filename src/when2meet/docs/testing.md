# When2Meet Testing

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
| `src/when2meet/modules/events/routes.py` | Public event API, authorization checks, participant update rules, error contracts. | 30% line coverage | 95% |
| `src/when2meet/modules/events/events_repo.py` | Event persistence, slug lookup, participant upsert/removal, owner/participant queries. | 30% line coverage | 98% |
| `src/when2meet/modules/events/schemas.py` | Request/response contracts and datetime normalization for slots and availability. | 30% line coverage | 99% |

The current evidence comes from:

```bash
uv run -m pytest tests/when2meet --cov=src/when2meet --cov-report=term-missing
```

The repository-wide coverage percentage may be lower when only `tests/when2meet` is executed because the monorepo contains other product services that are not part of this product-scoped evidence.

## Unit Tests

Unit tests for critical product logic are in:

- `tests/when2meet/test_event_schemas.py`

They cover:

- event slot normalization to UTC;
- deterministic sorting of event slots;
- participant availability normalization;
- rejection of unknown request fields;
- Innopolis name splitting used for participant display fallback.

## Integration Tests

Integration tests are in:

- `tests/when2meet/test_events.py`
- `tests/when2meet/test_when2meet_startup.py`

They cover important interactions between product components:

- FastAPI routes;
- authentication fixtures;
- mocked InNoHassle Accounts boundary;
- Beanie/MongoDB test infrastructure;
- event creation, retrieval, update, and deletion;
- participant availability updates and deletion;
- owner-only access control;
- not-found and invalid-request API contracts.

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

## Evidence Types

Pytest results are unit/integration test evidence.

Coverage reports are coverage evidence for critical modules.

The When2Meet secret scan workflow is additional QA check evidence.

QRT evidence must be kept separate from automated test, coverage, lint, type, build, link-checking, and secret-scanning evidence. Automated checks can support confidence in the product, but they do not replace QRT evidence unless the process requirements explicitly allow that specific evidence type.

## Maintenance

Tests added for Assignment 4 are maintained product assets. Later When2Meet changes must keep them passing or replace them with documented equivalent or stronger coverage when the product behavior changes.
