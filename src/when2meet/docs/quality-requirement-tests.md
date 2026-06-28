# Quality Requirement Tests

Automated quality requirement tests (QRTs) verify the measurable scenarios in [quality-requirements.md](quality-requirements.md). They run in CI through the repository pytest workflow ([`.github/workflows/tests.yaml`](../../../.github/workflows/tests.yaml)).

## QRT-001: Critical module line coverage

**Linked quality requirement:** [QR-001](quality-requirements.md#qr-001-critical-module-testability)

**Verification method:** Automated pytest check against CI `coverage.xml` output.

**Test data, setup, or environment:** Standard CI pytest job with `--cov-report=xml:coverage.xml` after When2Meet tests execute.

**Automated command or CI check:** `uv run -m pytest tests/when2meet/test_quality_requirements.py::test_qrt_critical_modules_line_coverage_meets_threshold` (included in the main pytest job).

**Expected measurable result:** Line coverage for each critical module is at least 30%.

**Evidence location:** [tests/when2meet/test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py); [latest tests CI run](https://github.com/one-zero-eight/monorepo/actions/runs/28267305034/job/83756940196).

## QRT-002: Owner-only event mutation

**Linked quality requirement:** [QR-002](quality-requirements.md#qr-002-owner-only-event-mutation)

**Verification method:** Automated integration tests against the FastAPI routes layer.

**Test data, setup, or environment:** TestClient with two authenticated users; one user creates an event, the other attempts mutation.

**Automated command or CI check:** `uv run -m pytest tests/when2meet/test_quality_requirements.py::test_qrt_non_owner_cannot_patch_or_delete_event`

**Expected measurable result:** Non-owner `PATCH` and `DELETE` requests return HTTP 403; owner deletion succeeds with HTTP 204.

**Evidence location:** [tests/when2meet/test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py); [latest tests CI run](https://github.com/one-zero-eight/monorepo/actions/runs/28267305034/job/83756940196).

## QRT-003: Event read response time

**Linked quality requirement:** [QR-003](quality-requirements.md#qr-003-event-read-response-time)

**Verification method:** Automated integration test with elapsed-time assertion.

**Test data, setup, or environment:** TestClient, authenticated owner, single event with two slots.

**Automated command or CI check:** `uv run -m pytest tests/when2meet/test_quality_requirements.py::test_qrt_get_event_completes_within_time_budget`

**Expected measurable result:** `GET /api/v0/events/{id}` completes in 2 seconds or less and returns HTTP 200.

**Evidence location:** [tests/when2meet/test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py); [latest tests CI run](https://github.com/one-zero-eight/monorepo/actions/runs/28267305034/job/83756940196).
