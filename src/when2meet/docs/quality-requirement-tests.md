# Quality Requirement Tests

Automated quality requirement tests (QRTs) verify the measurable scenarios in [quality-requirements.md](quality-requirements.md). They run in CI through the repository pytest workflow ([`.github/workflows/tests.yaml`](../../../.github/workflows/tests.yaml)).

## Contents

- [QRT-001: Critical module line coverage](#qrt-001-critical-module-line-coverage)
- [QRT-002: Owner-only event mutation](#qrt-002-owner-only-event-mutation)
- [QRT-003: Event read response time](#qrt-003-event-read-response-time)
- [QRT-004: QA documentation and architecture traceability](#qrt-004-qa-documentation-and-architecture-traceability)

## QRT-001: Critical module line coverage

**Linked quality requirement:** [QR-001](quality-requirements.md#qr-001-critical-module-testability)

**Verification method:** Automated pytest check against active coverage collection.

**Test data, setup, or environment:** Standard CI pytest job with `--cov=src/when2meet` while When2Meet tests execute.

**Automated command or CI check:** `uv run -m pytest tests/when2meet --cov=src/when2meet --cov-report=xml:coverage.xml`.

**Expected measurable result:** Line coverage for each critical module is at least 30%.

**Evidence location:** [tests/when2meet/test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py); [latest protected-main tests CI run](https://github.com/one-zero-eight/monorepo/actions/runs/29437789987).

## QRT-002: Owner-only event mutation

**Linked quality requirement:** [QR-002](quality-requirements.md#qr-002-owner-only-event-mutation)

**Verification method:** Automated integration tests against the FastAPI routes layer.

**Test data, setup, or environment:** TestClient with two authenticated users; one user creates an event, the other attempts mutation.

**Automated command or CI check:** `uv run -m pytest tests/when2meet/test_quality_requirements.py::test_qrt_non_owner_cannot_patch_or_delete_event`

**Expected measurable result:** Non-owner `PATCH` and `DELETE` requests return HTTP 403; owner deletion succeeds with HTTP 204.

**Evidence location:** [tests/when2meet/test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py); [latest protected-main tests CI run](https://github.com/one-zero-eight/monorepo/actions/runs/29437789987).

## QRT-003: Event read response time

**Linked quality requirement:** [QR-003](quality-requirements.md#qr-003-event-read-response-time)

**Verification method:** Automated integration test with elapsed-time assertion.

**Test data, setup, or environment:** TestClient, authenticated owner, single event with two slots.

**Automated command or CI check:** `uv run -m pytest tests/when2meet/test_quality_requirements.py::test_qrt_get_event_completes_within_time_budget`

**Expected measurable result:** `GET /api/v0/events/{id}` completes in 2 seconds or less and returns HTTP 200.

**Evidence location:** [tests/when2meet/test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py); [latest protected-main tests CI run](https://github.com/one-zero-eight/monorepo/actions/runs/29437789987).

## QRT-004: QA documentation and architecture traceability

**Linked quality requirement:** [QR-004](quality-requirements.md#qr-004-qa-evidence-traceability)

**Verification method:** Automated repository documentation test.

**Test data, setup, or environment:** Local checkout with maintained When2Meet docs under `src/when2meet/docs`, the architecture traceability mapping, and the accepted ADRs:

- [ADR-0001 Repository pattern for events persistence](architecture/adr/0001-repository-pattern-for-events-persistence.md)
- [ADR-0002 Slug-based public event references with ObjectId fallback](architecture/adr/0002-slug-based-public-event-references.md)
- [ADR-0003 InNoHassle Accounts JWT verification and user enrichment](architecture/adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md)

**Automated command or CI check:** `uv run -m pytest tests/when2meet/test_quality_requirements.py::test_qrt_qa_documentation_keeps_gates_and_architecture_traceability`

**Expected measurable result:** Required maintained docs include tables of contents; pytest, coverage, QRT, CI, and secret scan gates remain documented; QR/QRT IDs stay linked through the public and architecture quality-requirement evidence; accepted ADRs remain linked from quality requirement evidence; the Week 7 final report is linked from roadmap, handover, UAT, and the root README and preserves protected-default-branch CI evidence links.

**Evidence location:** [tests/when2meet/test_quality_requirements.py](../../../tests/when2meet/test_quality_requirements.py); [Week 7 final report](../reports/week7/README.md); latest tests CI run after merge.
