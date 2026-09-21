import pytest
import yaml

from src import common_config
from src.config_root_schema import Settings

_TEST_ACCOUNTS = {"api_jwt_token": "test-token"}


def test_accounts_mock_rejected_when_maps_not_development(tmp_path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        yaml.safe_dump(
            {
                "accounts": {**_TEST_ACCOUNTS, "mock": True},
                "maps_service": {"environment": "testing"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="accounts\\.mock"):
        Settings.from_yaml(settings_path)


def test_accounts_mock_accepted_when_all_development(tmp_path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        yaml.safe_dump(
            {
                "accounts": {**_TEST_ACCOUNTS, "mock": True},
                "maps_service": {"environment": "development"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    loaded = Settings.from_yaml(settings_path)
    assert loaded.accounts.mock is True


def test_accounts_mock_validates_clubs_and_student_affairs_environments():
    loaded = Settings.model_validate(
        {
            "accounts": {**_TEST_ACCOUNTS, "mock": True},
            "maps_service": {"environment": "development"},
            "clubs_service": {"environment": "development"},
            "student_affairs_service": {
                "environment": "development",
                "omnidesk": {"jwt_marker": "marker-0123456789abcdef"},
            },
        }
    )
    assert loaded.clubs_service is not None
    assert loaded.student_affairs_service is not None


def test_accounts_mock_rejected_when_clubs_not_development():
    with pytest.raises(ValueError, match="clubs_service"):
        Settings.model_validate(
            {
                "accounts": {**_TEST_ACCOUNTS, "mock": True},
                "maps_service": {"environment": "development"},
                "clubs_service": {"environment": "testing"},
            }
        )


def test_settings_from_yaml(tmp_path):
    settings_path = tmp_path / "settings.yaml"
    settings_path.write_text(
        yaml.safe_dump(
            {
                "$schema": "./settings.schema.yaml",
                "accounts": {"api_url": "https://api.innohassle.ru/accounts/v0", "api_jwt_token": "token"},
                "maps_service": {"environment": "testing"},
                "clubs_service": {"environment": "testing"},
                "student_affairs_service": {"environment": "testing", "omnidesk": {"jwt_marker": "marker-0123456789"}},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    loaded = Settings.from_yaml(settings_path)
    assert loaded.metrics is None
    assert loaded.maps_service.environment == "testing"
    assert loaded.clubs_service is not None
    assert loaded.clubs_service.environment == "testing"
    assert loaded.student_affairs_service is not None
    assert loaded.student_affairs_service.omnidesk.jwt_marker.get_secret_value() == "marker-0123456789"


@pytest.mark.parametrize("in_docker", [False, True], ids=["host", "docker"])
@pytest.mark.parametrize("explicit_url", [False, True], ids=["default", "override"])
def test_postgres_connection_settings(monkeypatch, in_docker, explicit_url):
    monkeypatch.setattr(common_config, "is_running_in_docker", lambda: in_docker)
    host = "postgres" if in_docker else "127.0.0.1"
    schedule_url = f"postgresql+asyncpg://postgres:postgres@{host}:5432/schedule"
    assistant_url = f"postgresql+psycopg://postgres:postgres@{host}:5432/schedule_assistant"
    schedule = {}
    assistant = {"api_key": "test-key", "booking": {"api_key": "test-booking-key"}}
    if explicit_url:
        schedule_url = "postgresql+asyncpg://custom:secret@db.example:5433/custom_schedule"
        assistant_url = "postgresql+psycopg://custom:secret@db.example:5433/custom_assistant"
        schedule["db_url"] = schedule_url
        assistant["db_url"] = assistant_url

    loaded = Settings.model_validate(
        {"accounts": _TEST_ACCOUNTS, "schedule_service": schedule, "schedule_assistant_service": assistant}
    )

    assert loaded.schedule_service is not None
    assert loaded.schedule_assistant_service is not None
    assert loaded.schedule_service.db_url.get_secret_value() == schedule_url
    assert loaded.schedule_assistant_service.db_url.get_secret_value() == assistant_url


def test_postgres_urls_optional_in_schema():
    definitions = Settings.model_json_schema()["$defs"]
    for service in ("ScheduleSettings", "ScheduleAssistantSettings"):
        assert "db_url" not in definitions[service].get("required", [])


def test_settings_save_schema(tmp_path):
    schema_path = tmp_path / "settings.schema.yaml"
    Settings.save_schema(schema_path)

    saved = yaml.safe_load(schema_path.read_text(encoding="utf-8"))
    assert saved["$schema"] == "https://json-schema.org/draft-07/schema"
    assert saved["title"] == "Settings"
    assert "properties" in saved
