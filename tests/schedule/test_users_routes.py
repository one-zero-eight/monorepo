from fastapi.testclient import TestClient

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
        params={"group_id": group["id"]},
        headers=user_headers,
    )
    assert add_response.status_code == 200
    assert group["id"] in add_response.json()["favorite_event_groups"]

    me_response = schedule_client.get("/users/me", headers=user_headers)
    assert group["id"] in me_response.json()["favorite_event_groups"]


def test_favorites_hide(schedule_client: TestClient, parser_headers: dict[str, str], user_headers: dict[str, str]):
    group = create_event_group(schedule_client, parser_headers, alias="hide-favorite-group")
    schedule_client.get("/users/me", headers=user_headers)
    schedule_client.post("/users/me/favorites", params={"group_id": group["id"]}, headers=user_headers)

    hide_response = schedule_client.post(
        "/users/me/favorites/hide",
        params={"group_id": group["id"], "hide": True},
        headers=user_headers,
    )
    assert hide_response.status_code == 200
    assert group["id"] in hide_response.json()["hidden_event_groups"]


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
