import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tests.schedule.conftest import create_event_group
from tests.schedule.constants import AUTH_REQUIRED_DETAIL, MAX_USER_ID, MIN_USER_ID, TEST_USER_EMAIL


def test_me_requires_auth(schedule_client: TestClient):
    response = schedule_client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_REQUIRED_DETAIL


def test_me_creates_user_on_first_auth(schedule_client: TestClient, user_headers: dict[str, str]):
    response = schedule_client.get("/users/me", headers=user_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == TEST_USER_EMAIL
    assert MIN_USER_ID <= body["id"] <= MAX_USER_ID


def test_me_predefined_empty(schedule_client: TestClient, user_headers: dict[str, str]):
    schedule_client.get("/users/me", headers=user_headers)
    response = schedule_client.get("/users/me/predefined", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["event_groups"] == []


def test_favorites_add_and_list(
    schedule_client: TestClient, parser_headers: dict[str, str], user_headers: dict[str, str]
):
    group = create_event_group(schedule_client, parser_headers, alias="favorite-group")
    schedule_client.get("/users/me", headers=user_headers)

    add_response = schedule_client.post(
        "/users/me/favorites",
        params={"group_alias": group["alias"]},
        headers=user_headers,
    )
    assert add_response.status_code == 200
    assert group["alias"] in add_response.json()["favorite_event_groups"]

    me_response = schedule_client.get("/users/me", headers=user_headers)
    assert group["alias"] in me_response.json()["favorite_event_groups"]


def test_favorites_hide(schedule_client: TestClient, parser_headers: dict[str, str], user_headers: dict[str, str]):
    group = create_event_group(schedule_client, parser_headers, alias="hide-favorite-group")
    schedule_client.get("/users/me", headers=user_headers)
    schedule_client.post("/users/me/favorites", params={"group_alias": group["alias"]}, headers=user_headers)

    hide_response = schedule_client.post(
        "/users/me/favorites/hide",
        params={"group_alias": group["alias"], "hide": True},
        headers=user_headers,
    )
    assert hide_response.status_code == 200
    assert group["alias"] in hide_response.json()["hidden_event_groups"]


def test_predefined_only_group_can_be_hidden(
    schedule_client: TestClient,
    user_headers: dict[str, str],
):
    from src.schedule.modules.predefined.storage import JsonPredefinedUsers
    from src.schedule.modules.predefined.utils import setup_predefined_data_from_object

    schedule_client.get("/users/me", headers=user_headers)
    setup_predefined_data_from_object(
        JsonPredefinedUsers(
            users=[JsonPredefinedUsers.InJsonUser(email=TEST_USER_EMAIL, groups=["predefined-only-group"])],
        )
    )

    hide_response = schedule_client.post(
        "/users/me/favorites/hide",
        params={"group_alias": "predefined-only-group", "hide": True},
        headers=user_headers,
    )
    assert hide_response.status_code == 200
    assert hide_response.json()["favorite_event_groups"] == []
    assert hide_response.json()["hidden_event_groups"] == ["predefined-only-group"]

    unhide_response = schedule_client.post(
        "/users/me/favorites/hide",
        params={"group_alias": "predefined-only-group", "hide": False},
        headers=user_headers,
    )
    assert unhide_response.status_code == 200
    assert unhide_response.json()["hidden_event_groups"] == []


def test_hide_rejects_group_outside_favorites_and_predefined(
    schedule_client: TestClient,
    user_headers: dict[str, str],
):
    schedule_client.get("/users/me", headers=user_headers)
    response = schedule_client.post(
        "/users/me/favorites/hide",
        params={"group_alias": "unknown-group", "hide": True},
        headers=user_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Favorite or predefined event group with alias unknown-group does not exist"


def test_set_moodle(schedule_client: TestClient, user_headers: dict[str, str]):
    schedule_client.get("/users/me", headers=user_headers)
    set_response = schedule_client.post(
        "/users/me/set-moodle",
        params={"moodle_userid": 42, "moodle_calendar_authtoken": "secret-token"},
        headers=user_headers,
    )
    assert set_response.status_code == 200

    me_response = schedule_client.get("/users/me", headers=user_headers)
    body = me_response.json()
    assert body["moodle_userid"] == 42
    assert body["moodle_calendar_authtoken"] == "secret-token"


def test_schedule_access_key_flow(schedule_client: TestClient, user_headers: dict[str, str]):
    schedule_client.get("/users/me", headers=user_headers)
    resource_path = "/users/me/all.ics"

    create_response = schedule_client.post(
        "/users/me/get-schedule-access-key",
        params={"resource_path": resource_path},
        headers=user_headers,
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["new"] is True
    access_key = payload["access_key"]["access_key"]

    list_response = schedule_client.get("/users/me/schedule-access-keys", headers=user_headers)
    assert list_response.status_code == 200
    keys = list_response.json()
    assert any(key["access_key"] == access_key for key in keys)

    delete_response = schedule_client.delete(
        "/users/me/schedule-access-key",
        params={"access_key": access_key, "resource_path": resource_path},
        headers=user_headers,
    )
    assert delete_response.status_code == 200

    list_after_delete = schedule_client.get("/users/me/schedule-access-keys", headers=user_headers)
    assert all(key["access_key"] != access_key for key in list_after_delete.json())


def test_virtual_favorite_is_persisted_by_alias(
    schedule_client: TestClient,
    user_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    from src.schedule.config import settings
    from src.schedule.config_schema import ScheduleAssistantIntegrationSettings

    api_url = "https://assistant.test"
    monkeypatch.setattr(
        settings,
        "schedule_assistant",
        ScheduleAssistantIntegrationSettings(api_url=api_url, api_key=SecretStr("service-key")),
    )
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(f"{api_url}/integration/event-groups").mock(
            return_value=httpx.Response(200, json=[{"alias": "virtual-favorite", "name": "Virtual"}])
        )
        response = schedule_client.post(
            "/users/me/favorites",
            params={"group_alias": "virtual-favorite"},
            headers=user_headers,
        )

    assert route.calls[0].request.headers["authorization"] == "Bearer service-key"
    assert response.status_code == 200
    assert response.json()["favorite_event_groups"] == ["virtual-favorite"]
