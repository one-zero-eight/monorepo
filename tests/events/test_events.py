from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from tests.events.helpers import create_and_publish, create_draft, fill_locales, future_iso, submit


def _white_png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_list_events_default_window(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    create_and_publish(events_client, user_headers, superadmin_headers)
    response = events_client.get("/events")
    assert response.status_code == 200
    events = response.json()
    assert len(events) == 1
    item = events[0]
    # list responses omit description
    assert all(locale.get("description") is None for locale in item["data"]["locales"].values())
    assert item["enrolled_count"] == 0
    # revision and approved_* are not populated for anonymous users
    assert item["revision"] is None
    assert item["approved_by"] is None
    assert item["approved_at"] is None


def test_list_events_from_to_filters(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    create_and_publish(events_client, user_headers, superadmin_headers, starts_at=future_iso(5))
    create_and_publish(events_client, user_headers, superadmin_headers, starts_at=future_iso(20))

    response = events_client.get("/events", params={"from": future_iso(10), "to": future_iso(30)})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_events_excludes_events_outside_default_window(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    create_and_publish(events_client, user_headers, superadmin_headers, starts_at=future_iso(45))
    response = events_client.get("/events")
    assert response.status_code == 200
    assert response.json() == []

    in_window = events_client.get("/events", params={"from": future_iso(40), "to": future_iso(50)})
    assert in_window.status_code == 200
    assert len(in_window.json()) == 1


def test_get_event_optional_auth(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    draft = create_and_publish(events_client, user_headers, superadmin_headers)
    response = events_client.get(f"/events/{draft['id']}")
    assert response.status_code == 200
    event = response.json()
    assert event["creator_id"] == "test-user-1"
    assert event["enrolled_count"] == 0
    assert event.get("enrolled") is None
    assert event.get("enrolled_users") is None
    assert event.get("revision") is None
    assert event.get("approved_by") is None


def test_enroll_and_unenroll(events_client: TestClient, user_headers: dict[str, str], superadmin_headers):
    draft = create_and_publish(events_client, user_headers, superadmin_headers)

    enrolled = events_client.post(f"/events/{draft['id']}/enroll", headers=user_headers)
    assert enrolled.status_code == 200
    assert enrolled.json()["enrolled"] is True
    assert enrolled.json()["enrolled_count"] == 1

    again = events_client.post(f"/events/{draft['id']}/enroll", headers=user_headers)
    assert again.status_code == 200
    assert again.json()["enrolled_count"] == 1  # user ids stay unique

    unenrolled = events_client.post(f"/events/{draft['id']}/unenroll", headers=user_headers)
    assert unenrolled.status_code == 200
    assert unenrolled.json()["enrolled"] is False
    assert unenrolled.json()["enrolled_count"] == 0


def test_enroll_requires_auth(events_client: TestClient, user_headers: dict[str, str], superadmin_headers):
    draft = create_and_publish(events_client, user_headers, superadmin_headers)
    response = events_client.post(f"/events/{draft['id']}/enroll")
    assert response.status_code == 401


def test_event_visibility_for_author_and_moderator(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    draft = create_and_publish(events_client, user_headers, superadmin_headers)
    events_client.post(f"/events/{draft['id']}/enroll", headers=user_headers)

    as_author = events_client.get(f"/events/{draft['id']}", headers=user_headers).json()
    assert as_author["enrolled_users"] == ["test-user-1"]
    assert as_author["revision"] is not None
    assert as_author["approved_at"] is not None
    assert as_author["approved_by"] is None  # only moderators see approved_by

    as_moderator = events_client.get(f"/events/{draft['id']}", headers=superadmin_headers).json()
    assert as_moderator["approved_by"] == "admin@innopolis.university"
    assert as_moderator["enrolled_users"] == ["test-user-1"]


def test_unpublish_by_moderator(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
    plain_user_headers: dict[str, str],
):
    draft = create_and_publish(events_client, user_headers, superadmin_headers)

    forbidden = events_client.delete(f"/events/{draft['id']}", headers=plain_user_headers)
    assert forbidden.status_code == 403

    response = events_client.delete(f"/events/{draft['id']}", headers=superadmin_headers)
    assert response.status_code == 200
    assert events_client.get(f"/events/{draft['id']}").status_code == 404

    draft_view = events_client.get(f"/drafts/{draft['id']}", headers=user_headers).json()
    assert draft_view["status"] == "unpublished"


def test_event_image_redirect(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    draft = create_draft(events_client, user_headers)
    upload = events_client.post(
        f"/drafts/{draft['id']}/image",
        files={"image_file": ("image.png", _white_png(), "image/png")},
        headers=user_headers,
    )
    assert upload.status_code == 200
    image_id = upload.json()["image_id"]

    fill_locales(events_client, draft["id"], user_headers)
    submit(events_client, draft["id"], user_headers)
    events_client.post(f"/submissions/{draft['id']}/approve", json={"feedback": ""}, headers=superadmin_headers)

    response = events_client.get(f"/events/{draft['id']}/image", follow_redirects=False)
    assert response.status_code == 307
    assert image_id in response.headers["location"]

    no_image = create_and_publish(events_client, user_headers, superadmin_headers)
    missing = events_client.get(f"/events/{no_image['id']}/image", follow_redirects=False)
    assert missing.status_code == 404
