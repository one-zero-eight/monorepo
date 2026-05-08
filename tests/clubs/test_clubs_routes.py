from io import BytesIO
from typing import Any, cast

import pytest
from fastapi import UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import Headers


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


def _club_payload(slug: str, title: str = "Test Club") -> dict:
    return {
        "slug": slug,
        "title": title,
        "short_description": "short",
        "description": "long",
        "type": "tech",
    }


def test_create_club_requires_auth(clubs_client: TestClient):
    response = clubs_client.post("/clubs/", json=_club_payload("clubs-access-test"))
    assert response.status_code == 401
    assert response.json()["detail"] == "Credentials not provided"


def test_create_club_forbidden_for_non_admin(clubs_client: TestClient, user_headers: dict[str, str]):
    response = clubs_client.post("/clubs/", json=_club_payload("clubs-access-test"), headers=user_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "You are not an admin in clubs service"


def test_create_club(clubs_client: TestClient, make_user_token, superadmin_headers: dict[str, str]):
    promote_response = clubs_client.post(
        "/users/change_role",
        params={
            "role": "admin",
            "user_to_change_email": "test-user-1@innopolis.university",
        },
        headers=superadmin_headers,
    )
    assert promote_response.status_code == 200

    admin_token = make_user_token(uid="test-user-1", email="test-user-1@innopolis.university")
    create_response = clubs_client.post(
        "/clubs/",
        json={
            "slug": "test-club",
            "title": "Test Club",
            "short_description": "club for integration tests",
            "description": "integration test club",
            "type": "tech",
            "leader_innohassle_id": "test-user-1",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["slug"] == "test-club"
    assert payload["leader_innohassle_id"] == "test-user-1"


def test_clubs_list_and_read_endpoints(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)

    empty_list = clubs_client.get("/clubs/")
    assert empty_list.status_code == 200
    assert empty_list.json() == []

    create_response = clubs_client.post("/clubs/", json=_club_payload("club-read"), headers=admin_headers)
    assert create_response.status_code == 200
    created = create_response.json()

    by_id = clubs_client.get(f"/clubs/by-id/{created['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["slug"] == "club-read"

    by_slug = clubs_client.get("/clubs/by-slug/club-read")
    assert by_slug.status_code == 200
    assert by_slug.json()["id"] == created["id"]

    list_after_create = clubs_client.get("/clubs/")
    assert list_after_create.status_code == 200
    assert len(list_after_create.json()) == 1


def test_clubs_get_returns_404_for_unknown_entities(clubs_client: TestClient):
    missing_by_id = clubs_client.get("/clubs/by-id/64b7de000000000000000001")
    assert missing_by_id.status_code == 404
    assert missing_by_id.json()["detail"] == "Club not found"

    missing_by_slug = clubs_client.get("/clubs/by-slug/no-such-club")
    assert missing_by_slug.status_code == 404
    assert missing_by_slug.json()["detail"] == "Club not found"


def test_clubs_edit_and_delete_flow(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)

    create_response = clubs_client.post("/clubs/", json=_club_payload("club-edit"), headers=admin_headers)
    assert create_response.status_code == 200
    created = create_response.json()

    edit_by_id = clubs_client.post(
        f"/clubs/by-id/{created['id']}",
        json=_club_payload("club-edit", title="Updated Title"),
        headers=admin_headers,
    )
    assert edit_by_id.status_code == 200
    assert edit_by_id.json()["title"] == "Updated Title"

    edit_by_slug = clubs_client.post(
        "/clubs/by-slug/club-edit",
        json=_club_payload("club-edit", title="Updated Again"),
        headers=admin_headers,
    )
    assert edit_by_slug.status_code == 200
    assert edit_by_slug.json()["title"] == "Updated Again"

    delete_response = clubs_client.delete(f"/clubs/by-id/{created['id']}", headers=admin_headers)
    assert delete_response.status_code == 200

    get_after_delete = clubs_client.get(f"/clubs/by-id/{created['id']}")
    assert get_after_delete.status_code == 404


def test_edit_club_rejects_unknown_new_leader(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    promote_response = clubs_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=superadmin_headers,
    )
    assert promote_response.status_code == 200

    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("leader-update-test"),
        headers=user_headers,
    )
    assert create_response.status_code == 200
    created_id = create_response.json()["id"]

    update_response = clubs_client.post(
        f"/clubs/by-id/{created_id}",
        json={
            **_club_payload("leader-update-test"),
            "new_leader_email": "unknown@innopolis.university",
        },
        headers=user_headers,
    )
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == "New leader email not found"


def test_edit_club_by_slug_rejects_unknown_new_leader(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    promote_response = clubs_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=superadmin_headers,
    )
    assert promote_response.status_code == 200

    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("leader-update-slug-test"),
        headers=user_headers,
    )
    assert create_response.status_code == 200

    update_response = clubs_client.post(
        "/clubs/by-slug/leader-update-slug-test",
        json={
            **_club_payload("leader-update-slug-test"),
            "new_leader_email": "unknown@innopolis.university",
        },
        headers=user_headers,
    )
    assert update_response.status_code == 404
    assert update_response.json()["detail"] == "New leader email not found"


def test_edit_club_by_id_returns_404_for_missing_club(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    response = clubs_client.post(
        "/clubs/by-id/64b7de000000000000000001",
        json=_club_payload("missing"),
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Club not found"


def test_edit_club_by_slug_returns_404_for_missing_club(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    response = clubs_client.post(
        "/clubs/by-slug/missing",
        json=_club_payload("missing"),
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Club not found"


def test_edit_club_sets_new_leader_by_id(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post("/clubs/", json=_club_payload("leader-by-id"), headers=admin_headers)
    assert create_response.status_code == 200
    created = create_response.json()

    update_response = clubs_client.post(
        f"/clubs/by-id/{created['id']}",
        json={**_club_payload("leader-by-id"), "new_leader_email": "test-user-1@innopolis.university"},
        headers=admin_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["leader_innohassle_id"] == "test-user-1"


def test_edit_club_sets_new_leader_by_slug(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post("/clubs/", json=_club_payload("leader-by-slug"), headers=admin_headers)
    assert create_response.status_code == 200

    update_response = clubs_client.post(
        "/clubs/by-slug/leader-by-slug",
        json={**_club_payload("leader-by-slug"), "new_leader_email": "test-user-1@innopolis.university"},
        headers=admin_headers,
    )
    assert update_response.status_code == 200
    assert update_response.json()["leader_innohassle_id"] == "test-user-1"


def test_delete_club_returns_404_for_missing_club(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    response = clubs_client.delete("/clubs/by-id/64b7de000000000000000001", headers=admin_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Club not found"


def test_get_logo_returns_404_for_missing_club(clubs_client: TestClient):
    response = clubs_client.get("/clubs/by-id/64b7de000000000000000001/logo", follow_redirects=False)
    assert response.status_code == 404
    assert response.json()["detail"] == "Club not found"


def test_get_logo_returns_404_when_logo_is_missing(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post("/clubs/", json=_club_payload("no-logo"), headers=admin_headers)
    assert create_response.status_code == 200
    created = create_response.json()

    response = clubs_client.get(f"/clubs/by-id/{created['id']}/logo", follow_redirects=False)
    assert response.status_code == 404
    assert response.json()["detail"] == "No logo available"


def test_get_logo_redirects_when_logo_exists(
    clubs_client: TestClient,
    monkeypatch,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    from src.clubs.modules.clubs import routes as clubs_routes

    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post("/clubs/", json=_club_payload("has-logo"), headers=admin_headers)
    assert create_response.status_code == 200
    created = create_response.json()

    edit_response = clubs_client.post(
        f"/clubs/by-id/{created['id']}",
        json={**_club_payload("has-logo"), "logo_file_id": "logo-123"},
        headers=admin_headers,
    )
    assert edit_response.status_code == 200
    monkeypatch.setattr(
        clubs_routes, "get_club_logo_url", lambda logo_file_id, size=None: f"https://cdn/{logo_file_id}/{size}"
    )

    response = clubs_client.get(f"/clubs/by-id/{created['id']}/logo", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://cdn/logo-123/512"


def test_set_logo_returns_404_for_missing_club(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    response = clubs_client.post(
        "/clubs/by-id/64b7de000000000000000001/logo",
        files={"logo_file": ("x.png", b"png", "image/png")},
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Club not found"


def test_set_logo_returns_400_for_invalid_content_type(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post("/clubs/", json=_club_payload("invalid-logo"), headers=admin_headers)
    assert create_response.status_code == 200
    created = create_response.json()

    response = clubs_client.post(
        f"/clubs/by-id/{created['id']}/logo",
        files={"logo_file": ("x.txt", b"not-image", "text/plain")},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "Invalid content type" in response.json()["detail"]


def test_set_logo_success(
    clubs_client: TestClient,
    monkeypatch,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    import pyvips

    from src.clubs.modules.clubs import routes as clubs_routes

    put_calls = []

    def _fake_put_club_logo(logo_file_id: str, size: int | None, data: bytes, content_type: str):
        put_calls.append((logo_file_id, size, data, content_type))

    monkeypatch.setattr(clubs_routes, "put_club_logo", _fake_put_club_logo)

    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post("/clubs/", json=_club_payload("good-logo"), headers=admin_headers)
    assert create_response.status_code == 200
    created = create_response.json()

    white_base = pyvips.Image.black(500, 500)
    white_image = cast(Any, white_base).new_from_image(255)
    white_png = cast(Any, white_image).write_to_buffer(".png")

    response = clubs_client.post(
        f"/clubs/by-id/{created['id']}/logo",
        files={"logo_file": ("x.png", white_png, "image/png")},
        headers=admin_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["logo_file_id"] is not None
    assert len(put_calls) == 2


@pytest.mark.asyncio
async def test_set_logo_content_type_detected_by_magic(monkeypatch):
    import pyvips
    from beanie import PydanticObjectId

    from src.clubs.modules.clubs import routes as clubs_routes

    class _FakeClub:
        logo_file_id = None

        async def save(self):
            return None

    async def _read_club(_id):
        return _FakeClub()

    monkeypatch.setattr(clubs_routes, "put_club_logo", lambda *args, **kwargs: None)
    monkeypatch.setattr(clubs_routes.clubs_repo, "read", _read_club)

    white_base = pyvips.Image.black(500, 500)
    white_image = cast(Any, white_base).new_from_image(255)
    white_png = cast(Any, white_image).write_to_buffer(".png")
    upload = UploadFile(
        file=BytesIO(white_png),
        filename="white.png",
        headers=Headers(),
    )

    result = await clubs_routes.set_club_logo(
        PydanticObjectId(),
        upload,
        cast(Any, object()),
    )
    assert result.logo_file_id is not None


def test_edit_club_by_slug_returns_400_when_revision_conflicts(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_first = clubs_client.post("/clubs/", json=_club_payload("update-conflict-a"), headers=admin_headers)
    assert create_first.status_code == 200
    create_second = clubs_client.post("/clubs/", json=_club_payload("update-conflict-b"), headers=admin_headers)
    assert create_second.status_code == 200

    response = clubs_client.post(
        "/clubs/by-slug/update-conflict-a",
        json=_club_payload("update-conflict-b"),
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Slug already exists"
