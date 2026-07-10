"""Automated quality requirement tests (QRT-001..QRT-004) for When2Meet."""

import re
import time as tm
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]

CRITICAL_MODULES = {
    "src/when2meet/modules/events/routes.py": 30.0,
    "src/when2meet/modules/events/events_repo.py": 30.0,
    "src/when2meet/modules/events/schemas.py": 30.0,
}

GET_EVENT_TIME_BUDGET_SECONDS = 2.0

DOCS_ROOT = REPO_ROOT / "src" / "when2meet" / "docs"
REQUIRED_MAINTAINED_DOCS = [
    DOCS_ROOT / "testing.md",
    DOCS_ROOT / "quality-requirements.md",
    DOCS_ROOT / "quality-requirement-tests.md",
    DOCS_ROOT / "definition-of-done.md",
    DOCS_ROOT / "architecture" / "quality-requirements.md",
]
REQUIRED_ADRS = [
    "architecture/adr/0001-repository-pattern-for-events-persistence.md",
    "architecture/adr/0002-slug-based-public-event-references.md",
    "architecture/adr/0003-inh-accounts-jwt-verification-and-user-enrichment.md",
]


def _line_rate_from_active_coverage(pytestconfig: pytest.Config, filename: str) -> float | None:
    cov_plugin = pytestconfig.pluginmanager.get_plugin("_cov")
    if cov_plugin is None or cov_plugin.cov_controller is None:
        return None

    module_path = REPO_ROOT / filename
    statements, _, _, missing, _ = cov_plugin.cov_controller.cov.analysis2(str(module_path))
    if not statements:
        return 100.0

    covered = len(statements) - len(missing)
    return covered / len(statements) * 100.0


def test_qrt_critical_modules_line_coverage_meets_threshold(pytestconfig: pytest.Config):
    """QRT-001 verifies QR-001 Testability coverage scenarios."""
    for module_path, minimum_percent in CRITICAL_MODULES.items():
        actual = _line_rate_from_active_coverage(pytestconfig, module_path)
        if actual is None:
            pytest.fail("active coverage data missing; run tests with --cov=src/when2meet")

        assert actual >= minimum_percent, (
            f"{module_path} line coverage {actual:.1f}% is below required {minimum_percent:.1f}%"
        )


def test_qrt_non_owner_cannot_patch_or_delete_event(
    when2meet_client: TestClient,
    user_headers,
    auth_header_factory,
):
    """QRT-002 verifies QR-002 Confidentiality for owner-only mutations."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "QRT Owner Event", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]

    other_headers = auth_header_factory("qrt-other-user", "qrt-other@example.com")

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}",
        json={"name": "Unauthorized rename"},
        headers=other_headers,
    )
    assert patch_resp.status_code == 403

    delete_resp = when2meet_client.delete(f"/api/v0/meetings/{event_id}", headers=other_headers)
    assert delete_resp.status_code == 403

    owner_delete_resp = when2meet_client.delete(f"/api/v0/meetings/{event_id}", headers=user_headers)
    assert owner_delete_resp.status_code == 204


def test_qrt_get_event_completes_within_time_budget(when2meet_client: TestClient, user_headers):
    """QRT-003 verifies QR-003 Time behaviour for event detail reads."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={
            "name": "QRT Timing Event",
            "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"],
        },
        headers=user_headers,
    )
    assert create_resp.status_code == 201
    event_id = create_resp.json()["id"]

    started = tm.monotonic()
    get_resp = when2meet_client.get(f"/api/v0/meetings/{event_id}", headers=user_headers)
    elapsed = tm.monotonic() - started

    assert get_resp.status_code == 200
    assert elapsed <= GET_EVENT_TIME_BUDGET_SECONDS


def test_qrt_qa_documentation_keeps_gates_and_architecture_traceability():
    """QRT-004 verifies QA evidence remains navigable and linked to architecture decisions."""
    for doc_path in REQUIRED_MAINTAINED_DOCS:
        text = doc_path.read_text()
        assert "## Contents" in text, f"{doc_path} must include a table of contents"

    testing_doc = (DOCS_ROOT / "testing.md").read_text()
    definition_of_done = (DOCS_ROOT / "definition-of-done.md").read_text()
    quality_requirements = (DOCS_ROOT / "quality-requirements.md").read_text()
    quality_requirement_tests = (DOCS_ROOT / "quality-requirement-tests.md").read_text()
    architecture_quality_requirements = (DOCS_ROOT / "architecture" / "quality-requirements.md").read_text()

    for gate in ["pytest", "coverage", "QRT", "secret scan", "CI"]:
        assert gate in testing_doc
        assert gate in definition_of_done

    for qr_id in ["QR-001", "QR-002", "QR-003", "QR-004"]:
        assert re.search(rf"## {qr_id}:", quality_requirements)
        assert qr_id in quality_requirement_tests
        assert qr_id in architecture_quality_requirements

    for qrt_id in ["QRT-001", "QRT-002", "QRT-003", "QRT-004"]:
        assert re.search(rf"## {qrt_id}:", quality_requirement_tests)
        assert qrt_id in quality_requirements
        assert qrt_id in architecture_quality_requirements

    for adr in REQUIRED_ADRS:
        assert adr in quality_requirements
        assert adr in quality_requirement_tests
        assert adr.replace("architecture/", "") in architecture_quality_requirements
