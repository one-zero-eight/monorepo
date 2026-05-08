# AGENTS.md

## Testing Principles

- Test behavior, not implementation details.
- Prefer meaningful integration tests for API routes and service flows.
- Add negative tests for every protected or validated path (auth, role, missing entities, invalid payloads).
- Keep mocks at external boundaries only (third-party APIs, object storage, heavy binary libs).
- Use real infrastructure when it gives confidence (e.g. Mongo via testcontainers), but isolate state per test.
- Centralize reusable test setup in `tests/conftest.py`; keep service-specific fixtures in `tests/<service>/conftest.py`.
- Keep tests deterministic: no network calls to real external services, no hidden environment coupling.
- Keep fixtures composable and explicit (`*_headers`, token factory, app client fixtures).
- Validate success and side effects where relevant (response + persisted state/observable result).
- Avoid "coverage-only" tests; each test should enforce a real contract.
- No tests for sake of test.
- Keep tests readable and small; extract helpers for repeated setup payloads.
- When fixing bugs found by tests, keep the regression test in place.

**Coverage Guidance**

- Coverage is a feedback signal, not the goal by itself.
- Prioritize low-coverage business-critical modules and error branches.
- Exclude non-business entrypoints (`__main__.py`) from coverage metrics.
- Keep route-level coverage high for auth, permissions, CRUD, and validation branches.
