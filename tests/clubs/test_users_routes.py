from fastapi.testclient import TestClient


def test_users_me_without_session(clubs_client: TestClient):
    response = clubs_client.get("/users/me")
    assert response.status_code == 401
    assert response.json()["detail"] == "Credentials not provided"


def test_users_me_with_session(clubs_client: TestClient, make_user_token):
    token = make_user_token(uid="test-user-1", email="test-user-1@innopolis.university")
    response = clubs_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["innohassle_id"] == "test-user-1"
    assert "leader_in_clubs" in payload


def test_users_me_with_expired_token(clubs_client: TestClient, make_user_token):
    token = make_user_token(uid="test-user-1", email="test-user-1@innopolis.university", expires_in_seconds=-1)
    response = clubs_client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Unable to verify credentials"


def test_users_me_with_malformed_token(clubs_client: TestClient):
    response = clubs_client.get("/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Unable to verify credentials"


def test_change_role_success_for_superadmin(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    response = clubs_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=superadmin_headers,
    )
    assert response.status_code == 200

    me_response = clubs_client.get("/users/me", headers=user_headers)
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "admin"


def test_change_role_updates_existing_user_record(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    make_admin = clubs_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=superadmin_headers,
    )
    assert make_admin.status_code == 200

    back_to_default = clubs_client.post(
        "/users/change_role",
        params={"role": "default", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=superadmin_headers,
    )
    assert back_to_default.status_code == 200

    me_response = clubs_client.get("/users/me", headers=user_headers)
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "default"


def test_change_role_forbidden_for_non_superadmin(clubs_client: TestClient, user_headers: dict[str, str]):
    response = clubs_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=user_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Only superadmin can change role"


def test_change_role_not_found_for_unknown_user(clubs_client: TestClient, superadmin_headers: dict[str, str]):
    response = clubs_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "absent@innopolis.university"},
        headers=superadmin_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "User to change not found"
