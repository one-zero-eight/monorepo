from fastapi.testclient import TestClient


def _admin_headers(
    clubs_client: TestClient, superadmin_headers: dict[str, str], user_headers: dict[str, str]
) -> dict[str, str]:
    response = clubs_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=superadmin_headers,
    )
    assert response.status_code == 200
    return user_headers


def _club_payload(slug: str, leader_id: str | None) -> dict:
    return {
        "slug": slug,
        "title": f"{slug} title",
        "short_description": "short",
        "description": "long",
        "type": "tech",
        "leader_innohassle_id": leader_id,
    }


def test_leaders_routes_for_existing_leader(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("leader-club", "test-user-1"),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    created = create_response.json()

    all_leaders = clubs_client.get("/leaders/")
    assert all_leaders.status_code == 200
    assert "test-user-1" in all_leaders.json()

    by_id = clubs_client.get(f"/leaders/by-club-id/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["innohassle_id"] == "test-user-1"

    by_slug = clubs_client.get("/leaders/by-club-slug/leader-club")
    assert by_slug.status_code == 200
    assert by_slug.json()["email"] == "test-user-1@innopolis.university"


def test_leaders_routes_for_club_without_leader(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("no-leader-club", None),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    created = create_response.json()

    by_id = clubs_client.get(f"/leaders/by-club-id/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json() is None

    by_slug = clubs_client.get("/leaders/by-club-slug/no-leader-club")
    assert by_slug.status_code == 200
    assert by_slug.json() is None


def test_leaders_routes_return_none_when_leader_user_missing(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("missing-leader-user", "missing-user"),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    created = create_response.json()

    by_id = clubs_client.get(f"/leaders/by-club-id/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json() is None


def test_leaders_routes_return_404_for_missing_club(clubs_client: TestClient):
    by_id = clubs_client.get("/leaders/by-club-id/64b7de000000000000000001")
    assert by_id.status_code == 404
    assert by_id.json()["detail"] == "Club not found"

    by_slug = clubs_client.get("/leaders/by-club-slug/no-such-club")
    assert by_slug.status_code == 404
    assert by_slug.json()["detail"] == "Club not found"
