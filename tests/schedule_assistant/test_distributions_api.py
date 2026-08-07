import datetime as dtm
import json
from pathlib import Path

import pytest
from httpx import AsyncClient

from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import (
    ScheduleConfig,
    ScheduleConfigUpdate,
    SectionConfig,
    StudentsGroups,
    TermConfig,
    TermPartialUpdate,
)

FIXTURES = Path(__file__).parent / "fixtures" / "distributions"


def _seed_config(repo: ScheduleConfigRepository) -> None:
    term = TermConfig(
        name="Spring 2026",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 1, 1),
            end_date=dtm.date(2026, 5, 31),
        ),
        sections=[
            SectionConfig(
                code="core",
                name="Core",
                kind="core",
                programs=[
                    SectionConfig.SectionProgram(
                        code="BS_Y1",
                        name="BS Y1",
                        groups=["B25-CSE-01", "B24-CBS-02"],
                    )
                ],
            ),
            SectionConfig(
                code="english",
                name="English",
                kind="english",
                programs=[
                    SectionConfig.SectionProgram(
                        code="EN",
                        name="English",
                        groups=["AWA-I 10", "EAP6"],
                    )
                ],
            ),
            SectionConfig(
                code="electives",
                name="Electives",
                kind="electives",
                programs=[
                    SectionConfig.SectionProgram(
                        code="EL",
                        name="Electives",
                        groups=["python-adv", "robotics"],
                    )
                ],
            ),
        ],
    )
    repo.set_config(
        ScheduleConfigUpdate(
            term=TermPartialUpdate.model_validate(term.model_dump()),
            students_groups=[
                StudentsGroups(code="B25-CSE-01", kind="core", students=["old@innopolis.university"]),
                StudentsGroups(code="B24-CBS-02", kind="core", students=[]),
                StudentsGroups(code="AWA-I 10", kind="english", students=[]),
                StudentsGroups(code="EAP6", kind="english", students=[]),
                StudentsGroups(code="python-adv", kind="elective", name="Углубленный Python", students=[]),
                StudentsGroups(code="robotics", kind="elective", name="Основы робототехники", students=[]),
                StudentsGroups(code="other-core", kind="core", students=["keep@innopolis.university"]),
            ],
            courses=[],
            rooms=[],
            instructors=[],
        ),
        saved_by="test@test.com",
    )


@pytest.mark.asyncio
async def test_preview_core_distribution(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    monkeypatch.setattr(
        "src.schedule_assistant.modules.distributions.routes.schedule_config_repository",
        schedule_config_repo,
    )
    _seed_config(schedule_config_repo)

    files = {
        "file": (
            "core.xlsx",
            (FIXTURES / "core_contingent.xlsx").read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    response = await authenticated_client.post(
        "/distributions/preview",
        data={"section_code": "core"},
        files=files,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["email_column"] == "Доменный идентификатор"
    assert payload["membership_columns"] == ["Учебная группа"]
    assert payload["stats"]["email_count"] == 3
    assert payload["suggested_mapping"]["B25-CSE-01"] == "B25-CSE-01"
    assert payload["suggested_mapping"]["B24-CBS-02"] == "B24-CBS-02"
    label = next(item for item in payload["labels"] if item["label"] == "B25-CSE-01")
    assert label["email_count"] == 2
    assert "emails" in label
    assert len(label["emails"]) == 2
    assert "sample_rows" not in payload


@pytest.mark.asyncio
async def test_apply_updates_only_mapped_groups(
    authenticated_client: AsyncClient,
    schedule_config_repo: ScheduleConfigRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    monkeypatch.setattr(
        "src.schedule_assistant.modules.distributions.routes.schedule_config_repository",
        schedule_config_repo,
    )
    _seed_config(schedule_config_repo)

    mapping = {
        "B25-CSE-01": "B25-CSE-01",
        "B24-CBS-02": None,
    }
    files = {
        "file": (
            "core.xlsx",
            (FIXTURES / "core_contingent.xlsx").read_bytes(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    response = await authenticated_client.post(
        "/distributions/apply",
        data={
            "section_code": "core",
            "mapping": json.dumps(mapping),
        },
        files=files,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["skipped_labels"] == ["B24-CBS-02"]
    assert len(payload["updated_groups"]) == 1
    assert payload["upload_id"]

    config: ScheduleConfig = schedule_config_repo.get_assembled()
    by_code = {group.code: group for group in config.students_groups}
    assert by_code["B25-CSE-01"].students == [
        "a.ivanov@innopolis.university",
        "p.petrov@innopolis.university",
    ]
    assert by_code["B24-CBS-02"].students == []
    assert by_code["other-core"].students == ["keep@innopolis.university"]

    history = await authenticated_client.get("/distributions/uploads", params={"section_code": "core"})
    assert history.status_code == 200, history.text
    items = history.json()
    assert len(items) == 1
    assert items[0]["id"] == payload["upload_id"]
    assert items[0]["filename"] == "core.xlsx"
    assert items[0]["stats"]["email_count"] == 3
    assert items[0]["stats"]["mapped_label_count"] == 1
    assert items[0]["updated_group_count"] == 1

    detail = await authenticated_client.get(f"/distributions/uploads/{payload['upload_id']}")
    assert detail.status_code == 200
    assert detail.json()["mapping"]["B25-CSE-01"] == "B25-CSE-01"
    assert detail.json()["skipped_labels"] == ["B24-CBS-02"]

    download = await authenticated_client.get(f"/distributions/uploads/{payload['upload_id']}/file")
    assert download.status_code == 200
    assert download.content[:2] == b"PK"
    assert "attachment" in download.headers.get("content-disposition", "")
