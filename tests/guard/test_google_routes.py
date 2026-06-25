from unittest.mock import AsyncMock, MagicMock

import pytest
from beanie import PydanticObjectId
from fastapi.testclient import TestClient

from src.guard.modules.google_.exceptions import FileNotFoundException, UserBannedException
from tests.guard.constants import GUARD_OTHER_OBJECT_ID

CREATE_FILE_PAYLOAD = {
    "file_type": "spreadsheet",
    "title": "My Sheet",
    "default_role": "reader",
    "owner_gmail": "owner@gmail.com",
}


@pytest.fixture
def mock_create_google_apis(monkeypatch: pytest.MonkeyPatch):
    from src.guard.modules.google_ import routes as google_routes

    monkeypatch.setattr(google_routes, "create_google_file", lambda **_kwargs: "google-new-file-id")
    monkeypatch.setattr(google_routes, "grant_owner_permission", lambda _file_id, _gmail: "owner-perm-1")
    monkeypatch.setattr(google_routes, "sheets_service", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr(google_routes, "update_file_title", lambda _file_id, _title: None)
    monkeypatch.setattr(google_routes, "revoke_file_permission", lambda _file_id, _perm_id: True)


def test_create_file_requires_auth(guard_client: TestClient):
    response = guard_client.post("/google/files", json=CREATE_FILE_PAYLOAD)
    assert response.status_code == 401
    assert response.json()["detail"] == "Credentials not provided"


def test_create_file(
    guard_client: TestClient,
    guard_author_headers: dict[str, str],
    mock_create_google_apis: None,
):
    response = guard_client.post("/google/files", json=CREATE_FILE_PAYLOAD, headers=guard_author_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == "google-new-file-id"
    assert body["join_link"].endswith("/join")


def test_list_files(
    guard_client: TestClient,
    guard_author_headers: dict[str, str],
    create_google_file,
):
    created = create_google_file()
    response = guard_client.get("/google/files", headers=guard_author_headers)
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()}
    assert created.slug in slugs


def test_get_file(
    guard_client: TestClient,
    guard_author_headers: dict[str, str],
    create_google_file,
):
    created = create_google_file()
    response = guard_client.get(f"/google/files/{created.slug}", headers=guard_author_headers)
    assert response.status_code == 200
    assert response.json()["slug"] == created.slug


def test_get_file_not_found(guard_client: TestClient, guard_author_headers: dict[str, str]):
    response = guard_client.get("/google/files/nonexistent-slug", headers=guard_author_headers)
    assert response.status_code == 404


def test_get_file_forbidden_for_other_user(
    guard_client: TestClient,
    guard_other_headers: dict[str, str],
    create_google_file,
):
    created = create_google_file()
    response = guard_client.get(f"/google/files/{created.slug}", headers=guard_other_headers)
    assert response.status_code == 403


def test_delete_file(
    guard_client: TestClient,
    guard_author_headers: dict[str, str],
    create_google_file,
):
    created = create_google_file()
    response = guard_client.delete(f"/google/files/{created.slug}", headers=guard_author_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "File deleted"

    get_response = guard_client.get(f"/google/files/{created.slug}", headers=guard_author_headers)
    assert get_response.status_code == 404


def test_delete_file_forbidden_for_other_user(
    guard_client: TestClient,
    guard_other_headers: dict[str, str],
    create_google_file,
):
    created = create_google_file()
    response = guard_client.delete(f"/google/files/{created.slug}", headers=guard_other_headers)
    assert response.status_code == 403


def test_patch_file_title(
    guard_client: TestClient,
    guard_author_headers: dict[str, str],
    create_google_file,
    mock_create_google_apis: None,
):
    created = create_google_file()
    response = guard_client.patch(
        f"/google/files/{created.slug}",
        json={"title": "Renamed Sheet"},
        headers=guard_author_headers,
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed Sheet"


def test_join_file_success(
    guard_client: TestClient,
    guard_other_headers: dict[str, str],
    create_google_file,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.guard.modules.google_ import routes as google_routes

    created = create_google_file()
    monkeypatch.setattr(google_routes, "add_user_to_file", AsyncMock(return_value=created))

    response = guard_client.post(
        f"/google/files/{created.slug}/joins",
        json={"gmail": "joiner@gmail.com"},
        headers=guard_other_headers,
    )
    assert response.status_code == 200
    assert "Successfully added" in response.json()["message"]


def test_join_file_user_banned(
    guard_client: TestClient,
    guard_other_headers: dict[str, str],
    create_google_file,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.guard.modules.google_ import routes as google_routes

    created = create_google_file()
    monkeypatch.setattr(
        google_routes,
        "add_user_to_file",
        AsyncMock(side_effect=UserBannedException(user_id=PydanticObjectId(GUARD_OTHER_OBJECT_ID))),
    )

    response = guard_client.post(
        f"/google/files/{created.slug}/joins",
        json={"gmail": "joiner@gmail.com"},
        headers=guard_other_headers,
    )
    assert response.status_code == 403
    assert "banned" in response.json()["detail"]


def test_join_file_not_found(
    guard_client: TestClient,
    guard_other_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
):
    from src.guard.modules.google_ import routes as google_routes

    monkeypatch.setattr(
        google_routes,
        "add_user_to_file",
        AsyncMock(side_effect=FileNotFoundException(slug="missing-slug")),
    )

    response = guard_client.post(
        "/google/files/missing-slug/joins",
        json={"gmail": "joiner@gmail.com"},
        headers=guard_other_headers,
    )
    assert response.status_code == 404


def test_ban_user(
    guard_client: TestClient,
    guard_portal,
    guard_author_headers: dict[str, str],
    create_google_file,
    mock_create_google_apis: None,
):
    created = create_google_file()
    other_id = PydanticObjectId(GUARD_OTHER_OBJECT_ID)

    async def _seed_join():
        from src.guard.modules.google_.repository import google_file_repository

        await google_file_repository.join_user_to_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
            role="reader",
            permission_id="perm-join-1",
        )

    guard_portal.call(_seed_join)

    response = guard_client.post(
        f"/google/files/{created.slug}/bans",
        json={"user_id": str(other_id)},
        headers=guard_author_headers,
    )
    assert response.status_code == 200
    assert "Successfully banned" in response.json()["message"]


def test_unban_user(
    guard_client: TestClient,
    guard_portal,
    guard_author_headers: dict[str, str],
    create_google_file,
):
    created = create_google_file()
    other_id = PydanticObjectId(GUARD_OTHER_OBJECT_ID)

    async def _seed_ban():
        from src.guard.modules.google_.repository import google_file_repository

        await google_file_repository.ban_user_from_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
        )

    guard_portal.call(_seed_ban)

    response = guard_client.delete(
        f"/google/files/{created.slug}/bans/{other_id}",
        headers=guard_author_headers,
    )
    assert response.status_code == 200
    assert "Successfully unbanned" in response.json()["message"]


def test_health_check(guard_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    from src.guard.modules.google_ import routes as google_routes

    monkeypatch.setattr(google_routes, "service_email", lambda: "guard-sa@test.local")

    response = guard_client.get("/google/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
