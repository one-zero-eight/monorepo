from fastapi.testclient import TestClient

from tests.events.conftest import CLUB_ID


def test_locales_returns_allowed_list(events_client: TestClient):
    response = events_client.get("/locales")
    assert response.status_code == 200
    assert response.json() == ["en", "ru"]


def test_users_me_requires_auth(events_client: TestClient):
    response = events_client.get("/users/me")
    assert response.status_code == 401


def test_users_me_event_manager(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.get("/users/me", headers=user_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["roles"] == ["event-manager"]
    assert payload["clubs"] == []


def test_users_me_club_leader(events_client: TestClient, club_leader_headers: dict[str, str]):
    response = events_client.get("/users/me", headers=club_leader_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["roles"] == ["club-leader"]
    assert payload["clubs"] == [{"club_id": CLUB_ID, "title": "Test Club"}]


def test_users_me_moderator(events_client: TestClient, superadmin_headers: dict[str, str]):
    response = events_client.get("/users/me", headers=superadmin_headers)
    assert response.status_code == 200
    assert response.json()["roles"] == ["moderator"]


def test_users_me_combined_roles(events_client: TestClient, make_user_token, clubs_owned_by):
    # test-user-1 is an event manager by email; give them a club to become a club leader too.
    clubs_owned_by["test-user-1"] = [{"club_id": CLUB_ID, "title": "Test Club"}]
    headers = {
        "Authorization": f"Bearer {make_user_token(uid='test-user-1', email='test-user-1@innopolis.university')}"
    }
    response = events_client.get("/users/me", headers=headers)
    assert response.status_code == 200
    assert set(response.json()["roles"]) == {"club-leader", "event-manager"}


def test_users_me_plain_user_has_no_roles(events_client: TestClient, plain_user_headers: dict[str, str]):
    response = events_client.get("/users/me", headers=plain_user_headers)
    assert response.status_code == 200
    assert response.json()["roles"] == []
    assert response.json()["clubs"] == []
