import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from src.schedule.modules.predefined.repository import predefined_repository
from src.schedule.modules.predefined.storage import JsonPredefinedUsers
from src.schedule.modules.predefined.utils import setup_predefined_data_from_object
from tests.schedule.conftest import create_event_group
from tests.schedule.constants import TEST_USER_EMAIL


def test_get_user_predefined_returns_group_aliases(
    schedule_client: TestClient,
    schedule_portal,
    parser_headers: dict[str, str],
    user_headers: dict[str, str],
):
    create_event_group(schedule_client, parser_headers, alias="predefined-target-group")
    me = schedule_client.get("/users/me", headers=user_headers).json()

    predefined = JsonPredefinedUsers(
        users=[JsonPredefinedUsers.InJsonUser(email=TEST_USER_EMAIL, groups=["predefined-target-group"])],
        academic_groups=[],
    )
    setup_predefined_data_from_object(predefined)

    group_aliases = schedule_portal.call(predefined_repository.get_user_predefined, me["id"])
    assert group_aliases == ["predefined-target-group"]


def test_get_user_predefined_combines_static_and_assistant(
    schedule_client: TestClient,
    schedule_portal,
    user_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule.config import settings
    from src.schedule.config_schema import ScheduleAssistantIntegrationSettings

    me = schedule_client.get("/users/me", headers=user_headers).json()
    setup_predefined_data_from_object(
        JsonPredefinedUsers(
            users=[JsonPredefinedUsers.InJsonUser(email=TEST_USER_EMAIL, groups=["static-group"])],
        )
    )
    api_url = "https://assistant.test"
    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url=api_url, api_key=SecretStr("service-key")),
    )
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(f"{api_url}/integration/users/{TEST_USER_EMAIL}/predefined").mock(
            return_value=httpx.Response(
                200,
                json={
                    "event_groups": [
                        "virtual-group",
                        "teacher-teacher@innopolis.university",
                        "static-group",
                    ]
                },
            )
        )
        aliases = schedule_portal.call(predefined_repository.get_user_predefined, me["id"])

    assert route.called
    assert aliases == [
        "static-group",
        "virtual-group",
        "teacher-teacher@innopolis.university",
    ]
