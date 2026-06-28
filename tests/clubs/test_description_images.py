from io import BytesIO
from urllib.parse import urlparse

from fastapi.testclient import TestClient
from PIL import Image

from src.clubs.modules.clubs.description_images_repo import description_images_repo


def _white_png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


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


def _club_payload(slug: str, leader_id: str | None = None) -> dict:
    payload = {
        "slug": slug,
        "title": "Test Club",
        "short_description": "short",
        "description": "long",
        "type": "tech",
    }
    if leader_id is not None:
        payload["leader_innohassle_id"] = leader_id
    return payload


def test_get_description_image_object_name(clubs_client: TestClient):
    assert description_images_repo.get_object_name("abc") == "description-images/abc"


def test_get_description_image_url(clubs_client: TestClient):
    url = description_images_repo.get_url("img-1")
    parsed = urlparse(url)
    assert parsed.scheme in {"http", "https"}
    assert "description-images/img-1" in url


def test_put_description_image(clubs_client: TestClient):
    description_images_repo.put("img-2", b"webp-bytes", "image/webp")

    obj = description_images_repo.minio_client.get_object(description_images_repo.bucket, "description-images/img-2")
    try:
        assert obj.read() == b"webp-bytes"
    finally:
        obj.close()
        obj.release_conn()


def test_description_image_exists(clubs_client: TestClient):
    assert description_images_repo.exists("missing-image") is False
    description_images_repo.put("exists-image", b"webp-bytes", "image/webp")
    assert description_images_repo.exists("exists-image") is True


def test_upload_description_image_requires_auth(clubs_client: TestClient):
    response = clubs_client.post(
        "/clubs/by-id/64b7de000000000000000001/description-images",
        files={"image_file": ("x.png", _white_png(), "image/png")},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Credentials not provided"


def test_upload_description_image_forbidden_for_non_leader(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
    auth_header_factory,
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("desc-img-forbidden", leader_id="test-user-1"),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    club_id = create_response.json()["id"]

    other_headers = auth_header_factory("507f1f77bcf86cd799439012", "guard-other@innopolis.university")
    response = clubs_client.post(
        f"/clubs/by-id/{club_id}/description-images",
        files={"image_file": ("x.png", _white_png(), "image/png")},
        headers=other_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Only club leader or admin can upload description images"


def test_upload_description_image_as_leader(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("desc-img-leader", leader_id="test-user-1"),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    club_id = create_response.json()["id"]

    response = clubs_client.post(
        f"/clubs/by-id/{club_id}/description-images",
        files={"image_file": ("x.png", _white_png(), "image/png")},
        headers=user_headers,
    )
    assert response.status_code == 200
    image_id = response.json()["image_id"]
    assert image_id is not None
    assert description_images_repo.exists(image_id) is True


def test_upload_description_image_as_admin(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("desc-img-admin", leader_id="507f1f77bcf86cd799439011"),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    club_id = create_response.json()["id"]

    response = clubs_client.post(
        f"/clubs/by-id/{club_id}/description-images",
        files={"image_file": ("x.png", _white_png(), "image/png")},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["image_id"] is not None


def test_upload_description_image_returns_404_for_missing_club(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    response = clubs_client.post(
        "/clubs/by-id/64b7de000000000000000001/description-images",
        files={"image_file": ("x.png", _white_png(), "image/png")},
        headers=admin_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Club not found"


def test_upload_description_image_returns_400_for_invalid_content_type(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("desc-img-invalid", leader_id="test-user-1"),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    club_id = create_response.json()["id"]

    response = clubs_client.post(
        f"/clubs/by-id/{club_id}/description-images",
        files={"image_file": ("x.txt", b"not-image", "text/plain")},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "Invalid content type" in response.json()["detail"]


def test_upload_description_image_converts_to_webp(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("desc-img-webp", leader_id="test-user-1"),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    club_id = create_response.json()["id"]

    response = clubs_client.post(
        f"/clubs/by-id/{club_id}/description-images",
        files={"image_file": ("x.png", _white_png(), "image/png")},
        headers=admin_headers,
    )
    assert response.status_code == 200
    image_id = response.json()["image_id"]

    obj = description_images_repo.minio_client.get_object(
        description_images_repo.bucket,
        description_images_repo.get_object_name(image_id),
    )
    try:
        data = obj.read()
        assert len(data) > 0
        assert data[:4] == b"RIFF"
    finally:
        obj.close()
        obj.release_conn()


def test_get_description_image_is_public(
    clubs_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    admin_headers = _admin_headers(clubs_client, superadmin_headers, user_headers)
    create_response = clubs_client.post(
        "/clubs/",
        json=_club_payload("desc-img-public", leader_id="test-user-1"),
        headers=admin_headers,
    )
    assert create_response.status_code == 200
    club_id = create_response.json()["id"]

    upload_response = clubs_client.post(
        f"/clubs/by-id/{club_id}/description-images",
        files={"image_file": ("x.png", _white_png(), "image/png")},
        headers=admin_headers,
    )
    assert upload_response.status_code == 200
    image_id = upload_response.json()["image_id"]

    response = clubs_client.get(f"/clubs/description-images/{image_id}", follow_redirects=False)
    assert response.status_code == 307
    loc = response.headers["location"]
    parsed = urlparse(loc)
    assert parsed.scheme in {"http", "https"}
    assert f"description-images/{image_id}" in loc


def test_get_description_image_returns_404_when_missing(clubs_client: TestClient):
    response = clubs_client.get("/clubs/description-images/missing-image", follow_redirects=False)
    assert response.status_code == 404
    assert response.json()["detail"] == "Image not found"
