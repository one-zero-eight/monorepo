from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from tests.events.helpers import add_external_host, assert_resolved_location, create_draft, fill_locales, submit


def _white_png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _ready_draft(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    created = create_draft(client, headers, **overrides)
    add_external_host(client, created["id"], headers)
    fill_locales(client, created["id"], headers)
    return created


def test_submit_incomplete_draft_rejected(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    response = events_client.post(f"/submissions/{created['id']}", headers=user_headers)
    assert response.status_code == 400
    body = response.json()["detail"]
    assert "locale" in body or "Hosts" in body


def test_submit_and_get_pending(events_client: TestClient, user_headers: dict[str, str]):
    created = _ready_draft(events_client, user_headers)
    response = submit(events_client, created["id"], user_headers)
    assert response["status"] == "pending"
    assert response["submission"]["moderation"]["status"] == "pending"
    assert len(response["submission"]["data"]["hosts"]) == 1
    assert response["submission"]["data"]["duration_hours"] == 2.0
    assert response["submission"]["data"]["enrollment"]["type"] == "internal"

    draft = events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()
    assert response["submission"]["data"]["starts_at"] == draft["data"]["starts_at"]
    assert draft["status"] == "pending"

    got = events_client.get(f"/submissions/{created['id']}", headers=user_headers).json()
    assert got["status"] == "pending"


def test_resubmit_requires_changes(events_client: TestClient, user_headers: dict[str, str]):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)
    response = events_client.post(f"/submissions/{created['id']}", headers=user_headers)
    assert response.status_code == 400
    assert "has not changed" in response.json()["detail"]

    events_client.patch(f"/drafts/{created['id']}", json={"location": "changed"}, headers=user_headers)
    resubmit = events_client.post(f"/submissions/{created['id']}", headers=user_headers)
    assert resubmit.status_code == 200
    assert_resolved_location(resubmit.json()["submission"]["data"]["location"], "changed", on_map=False)


def test_approve_publishes_event(events_client: TestClient, user_headers, superadmin_headers):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)
    response = events_client.post(
        f"/submissions/{created['id']}/approve",
        json={"feedback": ""},
        headers=superadmin_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    submission = body["submission"]
    assert submission["moderation"]["status"] == "approved"

    event = events_client.get(f"/events/{created['id']}").json()
    assert event["data"]["locales"]["en"]["name"] == "Event en"

    draft = events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()
    assert draft["status"] == "published"


def test_approve_requires_moderator(events_client: TestClient, user_headers: dict[str, str]):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)
    response = events_client.post(f"/submissions/{created['id']}/approve", json={"feedback": ""}, headers=user_headers)
    assert response.status_code == 403


def test_decline_requires_feedback(events_client: TestClient, user_headers, superadmin_headers):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)

    missing = events_client.post(f"/submissions/{created['id']}/decline", json={}, headers=superadmin_headers)
    assert missing.status_code == 422

    declined = events_client.post(
        f"/submissions/{created['id']}/decline",
        json={"feedback": "needs work"},
        headers=superadmin_headers,
    )
    assert declined.status_code == 200
    body = declined.json()
    assert body["status"] == "declined"
    moderation = body["submission"]["moderation"]
    assert moderation["status"] == "declined"
    assert moderation["feedback"] == "needs work"

    draft = events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()
    assert draft["status"] == "declined"


def test_approve_after_decline_overrides_public(events_client: TestClient, user_headers, superadmin_headers):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)
    events_client.post(
        f"/submissions/{created['id']}/decline",
        json={"feedback": "first version rejected"},
        headers=superadmin_headers,
    )
    events_client.patch(f"/drafts/{created['id']}", json={"location": "fixed"}, headers=user_headers)
    submit(events_client, created["id"], user_headers)
    response = events_client.post(
        f"/submissions/{created['id']}/approve", json={"feedback": ""}, headers=superadmin_headers
    )
    assert response.status_code == 200
    event = events_client.get(f"/events/{created['id']}").json()
    assert_resolved_location(event["data"]["location"], "fixed", on_map=False)


def test_submission_status_unpublished_after_unpublish(events_client: TestClient, user_headers, superadmin_headers):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)
    events_client.post(f"/submissions/{created['id']}/approve", json={"feedback": ""}, headers=superadmin_headers)

    events_client.delete(f"/events/{created['id']}", headers=superadmin_headers)

    submission = events_client.get(f"/submissions/{created['id']}", headers=user_headers).json()
    assert submission["submission"]["moderation"]["status"] == "approved"
    assert submission["status"] == "unpublished"

    # Draft edits must not hide unpublished on the submission view
    events_client.patch(f"/drafts/{created['id']}", json={"location": "edited after unpublish"}, headers=user_headers)
    assert events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()["status"] is None
    assert events_client.get(f"/submissions/{created['id']}", headers=user_headers).json()["status"] == "unpublished"

    listed = events_client.get("/submissions", headers=user_headers).json()
    assert any(item["id"] == created["id"] and item["status"] == "unpublished" for item in listed)


def test_delete_pending_submission(events_client: TestClient, user_headers: dict[str, str]):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)
    response = events_client.delete(f"/submissions/{created['id']}", headers=user_headers)
    assert response.status_code == 200
    draft = events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()
    assert draft["status"] is None


def test_delete_non_pending_submission_forbidden(events_client: TestClient, user_headers, superadmin_headers):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)
    events_client.post(f"/submissions/{created['id']}/decline", json={"feedback": "no"}, headers=superadmin_headers)
    response = events_client.delete(f"/submissions/{created['id']}", headers=user_headers)
    assert response.status_code == 400
    assert "pending" in response.json()["detail"]


def test_list_submissions_filter_by_status(events_client: TestClient, user_headers, superadmin_headers):
    draft_ids = []
    for _ in range(2):
        created = _ready_draft(events_client, user_headers)
        submit(events_client, created["id"], user_headers)
        draft_ids.append(created["id"])
    events_client.post(f"/submissions/{draft_ids[0]}/approve", json={"feedback": ""}, headers=superadmin_headers)

    all_submissions = events_client.get("/submissions", headers=superadmin_headers).json()
    assert len(all_submissions) == 2
    assert all_submissions[0]["submission"]["data"]["name"] == "Event en"
    assert "locales" not in all_submissions[0]["submission"]["data"]
    by_id = {item["id"]: item for item in all_submissions}
    assert by_id[draft_ids[0]]["status"] == "published"
    assert by_id[draft_ids[1]]["status"] == "pending"
    pending = events_client.get("/submissions", params={"status": "pending"}, headers=superadmin_headers).json()
    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    approved = events_client.get("/submissions", params={"status": "approved"}, headers=superadmin_headers).json()
    assert len(approved) == 1
    assert approved[0]["status"] == "published"


def test_list_submissions_own_only(events_client: TestClient, user_headers, club_leader_headers, superadmin_headers):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)

    own = events_client.get("/submissions", headers=user_headers).json()
    assert len(own) == 1
    other = events_client.get("/submissions", headers=club_leader_headers).json()
    assert other == []


def test_get_submission_visibility(events_client: TestClient, user_headers, plain_user_headers, superadmin_headers):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)

    assert events_client.get(f"/submissions/{created['id']}", headers=user_headers).status_code == 200
    assert events_client.get(f"/submissions/{created['id']}", headers=superadmin_headers).status_code == 200
    assert events_client.get(f"/submissions/{created['id']}", headers=plain_user_headers).status_code == 404


def test_submission_image_redirect(events_client: TestClient, user_headers: dict[str, str]):
    created = _ready_draft(events_client, user_headers)
    submit(events_client, created["id"], user_headers)

    no_image = events_client.get(f"/submissions/{created['id']}/image", follow_redirects=False)
    assert no_image.status_code == 404

    events_client.delete(f"/submissions/{created['id']}", headers=user_headers)
    upload = events_client.post(
        f"/drafts/{created['id']}/image",
        files={"image_file": ("image.png", _white_png(), "image/png")},
        headers=user_headers,
    )
    assert upload.status_code == 200
    image_id = upload.json()["image_id"]
    submit(events_client, created["id"], user_headers)

    response = events_client.get(f"/submissions/{created['id']}/image", follow_redirects=False)
    assert response.status_code == 307
    assert image_id in response.headers["location"]
