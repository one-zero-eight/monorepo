"""Service-to-service integration endpoint: clubs owned by a user (API key auth)."""

from fastapi.testclient import TestClient


def _promote_and_create_club(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
    slug: str,
) -> dict:
    promote = clubs_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=superadmin_headers,
    )
    assert promote.status_code == 200

    created = clubs_client.post(
        "/clubs/",
        json={
            "slug": slug,
            "title": "Integration Club",
            "short_description": "short",
            "description": "long",
            "type": "tech",
            "leader_innohassle_id": "test-user-1",
        },
        headers=user_headers,
    )
    assert created.status_code == 200
    return created.json()


def test_owned_by_requires_api_key(clubs_client: TestClient):
    response = clubs_client.get("/clubs/owned-by/test-user-1")
    assert response.status_code == 401


def test_owned_by_rejects_wrong_api_key(clubs_client: TestClient):
    response = clubs_client.get(
        "/clubs/owned-by/test-user-1",
        headers={"Authorization": "Bearer wrong-api-key"},
    )
    assert response.status_code == 401


def test_owned_by_returns_clubs_of_user(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    club = _promote_and_create_club(clubs_client, superadmin_headers, user_headers, "owned-by-test")
    headers = {"Authorization": "Bearer test-clubs-api-key"}

    owned = clubs_client.get("/clubs/owned-by/test-user-1", headers=headers)
    assert owned.status_code == 200
    assert owned.json() == [{"club_id": club["id"], "title": "Integration Club"}]

    other = clubs_client.get("/clubs/owned-by/someone-else", headers=headers)
    assert other.status_code == 200
    assert other.json() == []
