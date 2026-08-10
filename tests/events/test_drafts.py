from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from tests.events.conftest import CLUB_ID, CLUB_ID_2
from tests.events.helpers import (
    add_club_host,
    add_external_host,
    create_and_publish,
    create_draft,
    draft_payload,
    fill_locales,
    future_iso,
    past_iso,
    submit,
)


def _white_png() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (32, 32), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def test_create_draft_requires_auth(events_client: TestClient):
    response = events_client.post("/drafts", json=draft_payload())
    assert response.status_code == 401


def test_create_draft_forbidden_for_plain_user(events_client: TestClient, plain_user_headers: dict[str, str]):
    response = events_client.post("/drafts", json=draft_payload(), headers=plain_user_headers)
    assert response.status_code == 403
    assert "Only club leaders or event managers" in response.json()["detail"]


def test_create_draft_starts_without_hosts(events_client: TestClient, club_leader_headers: dict[str, str]):
    response = events_client.post("/drafts", json=draft_payload(), headers=club_leader_headers)
    assert response.status_code == 200
    draft = response.json()
    assert draft["creator_id"] == "club-leader-1"
    assert draft["status"] is None
    assert draft["data"]["hosts"] == []
    assert draft["invitations"] == []
    assert draft["can_edit"] is True
    assert set(draft["data"]["locales"]) == {"en", "ru"}
    assert draft["data"]["duration_hours"] == 2.0
    assert draft["data"]["enrollment"] == {"type": "internal", "url": None, "capacity": None}


def test_create_draft_as_event_manager(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.post("/drafts", json=draft_payload(), headers=user_headers)
    assert response.status_code == 200
    assert response.json()["data"]["hosts"] == []


def test_add_club_host(events_client: TestClient, club_leader_headers: dict[str, str]):
    created = create_draft(events_client, club_leader_headers)
    draft = add_club_host(events_client, created["id"], club_leader_headers)
    assert len(draft["data"]["hosts"]) == 1
    host = draft["data"]["hosts"][0]
    assert host["type"] == "club"
    assert host["club_id"] == CLUB_ID
    assert host["id"]


def test_add_club_host_must_be_owned(events_client: TestClient, club_leader_headers: dict[str, str]):
    created = create_draft(events_client, club_leader_headers)
    response = events_client.post(
        f"/drafts/{created['id']}/hosts/clubs",
        json={"club_id": "64b7de000000000000000999"},
        headers=club_leader_headers,
    )
    assert response.status_code == 400
    assert "not a leader" in response.json()["detail"]


def test_add_external_host_event_manager_only(
    events_client: TestClient, user_headers: dict[str, str], club_leader_headers: dict[str, str]
):
    created = create_draft(events_client, club_leader_headers)
    forbidden = events_client.post(
        f"/drafts/{created['id']}/hosts/external",
        json={"name": "External"},
        headers=club_leader_headers,
    )
    assert forbidden.status_code == 403

    manager_draft = create_draft(events_client, user_headers)
    draft = add_external_host(events_client, manager_draft["id"], user_headers)
    assert draft["data"]["hosts"][0]["type"] == "external"
    assert draft["data"]["hosts"][0]["name"] == "One Zero Eight"


def test_create_draft_rejects_unknown_locale(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.post("/drafts", json=draft_payload(locales=["de"]), headers=user_headers)
    assert response.status_code == 400
    assert "not in the allowed list" in response.json()["detail"]


def test_drafts_are_private_to_author(events_client: TestClient, club_leader_headers, plain_user_headers):
    created = create_draft(events_client, club_leader_headers)
    missing = events_client.get(f"/drafts/{created['id']}", headers=plain_user_headers)
    assert missing.status_code == 404
    own = events_client.get(f"/drafts/{created['id']}", headers=club_leader_headers)
    assert own.status_code == 200


def test_invite_accept_and_list_invited_by(
    events_client: TestClient,
    club_leader_headers: dict[str, str],
    other_club_leader_headers: dict[str, str],
):
    created = create_draft(events_client, club_leader_headers)
    add_club_host(events_client, created["id"], club_leader_headers)

    invited = events_client.post(
        f"/drafts/{created['id']}/hosts/invitations",
        json={"club_id": CLUB_ID_2},
        headers=club_leader_headers,
    )
    assert invited.status_code == 200
    assert invited.json()["invitations"] == [CLUB_ID_2]

    as_invitee = events_client.get(f"/drafts/{created['id']}", headers=other_club_leader_headers)
    assert as_invitee.status_code == 200
    assert as_invitee.json()["can_edit"] is False

    listed = events_client.get("/drafts", headers=other_club_leader_headers).json()
    assert len(listed) == 1
    assert listed[0]["invited_by"] == "Club Leader One"

    accepted = events_client.post(f"/drafts/{created['id']}/accept", headers=other_club_leader_headers)
    assert accepted.status_code == 200
    assert accepted.json()["invitations"] == []
    assert accepted.json()["can_edit"] is True
    assert any(h["club_id"] == CLUB_ID_2 for h in accepted.json()["data"]["hosts"])

    listed_after = events_client.get("/drafts", headers=other_club_leader_headers).json()
    assert listed_after[0].get("invited_by") is None


def test_decline_invitation(
    events_client: TestClient,
    club_leader_headers: dict[str, str],
    other_club_leader_headers: dict[str, str],
):
    created = create_draft(events_client, club_leader_headers)
    events_client.post(
        f"/drafts/{created['id']}/hosts/invitations",
        json={"club_id": CLUB_ID_2},
        headers=club_leader_headers,
    )
    declined = events_client.post(f"/drafts/{created['id']}/decline", headers=other_club_leader_headers)
    assert declined.status_code == 200
    assert declined.json()["invitations"] == []
    assert events_client.get(f"/drafts/{created['id']}", headers=other_club_leader_headers).status_code == 404


def test_list_drafts_shows_accessible(events_client: TestClient, club_leader_headers, user_headers):
    create_draft(events_client, club_leader_headers)
    create_draft(events_client, user_headers)

    leader_drafts = events_client.get("/drafts", headers=club_leader_headers).json()
    manager_drafts = events_client.get("/drafts", headers=user_headers).json()
    assert len(leader_drafts) == 1
    assert len(manager_drafts) == 1
    assert "locales" not in manager_drafts[0]["data"]
    assert manager_drafts[0]["data"]["name"] is None


def test_patch_draft_data(events_client: TestClient, club_leader_headers: dict[str, str]):
    created = create_draft(events_client, club_leader_headers)
    response = events_client.patch(
        f"/drafts/{created['id']}",
        json={"starts_at": future_iso(14), "location": "109", "duration_hours": 3.5},
        headers=club_leader_headers,
    )
    assert response.status_code == 200
    draft = response.json()
    assert draft["data"]["location"] == "109"
    assert draft["data"]["duration_hours"] == 3.5
    assert draft["revision"] != created["revision"]


def test_host_order_and_delete(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    add_external_host(events_client, created["id"], user_headers, name="A")
    draft = add_external_host(events_client, created["id"], user_headers, name="B")
    ids = [h["id"] for h in draft["data"]["hosts"]]
    assert len(ids) == 2

    reordered = events_client.put(
        f"/drafts/{created['id']}/hosts/order",
        json={"host_ids": list(reversed(ids))},
        headers=user_headers,
    )
    assert reordered.status_code == 200
    assert [h["id"] for h in reordered.json()["data"]["hosts"]] == list(reversed(ids))

    deleted = events_client.delete(f"/drafts/{created['id']}/hosts/{ids[0]}", headers=user_headers)
    assert deleted.status_code == 200
    assert len(deleted.json()["data"]["hosts"]) == 1


def test_put_locale_autocreates_and_validates(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers, locales=["en"])
    response = events_client.put(
        f"/drafts/{created['id']}/locales/ru",
        json={"name": "Событие", "description": None},
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["locales"]["ru"] == {"name": "Событие", "description": None}

    empty_ok = events_client.put(
        f"/drafts/{created['id']}/locales/ru",
        json={"name": "", "description": ""},
        headers=user_headers,
    )
    assert empty_ok.status_code == 200
    assert empty_ok.json()["data"]["locales"]["ru"] == {"name": "", "description": ""}

    missing_field = events_client.put(
        f"/drafts/{created['id']}/locales/ru",
        json={"name": "x"},
        headers=user_headers,
    )
    assert missing_field.status_code == 422

    invalid = events_client.put(
        f"/drafts/{created['id']}/locales/de",
        json={"name": "x", "description": "y"},
        headers=user_headers,
    )
    assert invalid.status_code == 400


def test_delete_locale(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers, locales=["en", "ru"])
    response = events_client.delete(f"/drafts/{created['id']}/locales/ru", headers=user_headers)
    assert response.status_code == 200
    assert "ru" not in response.json()["data"]["locales"]


def test_can_submit_reports_guardrail_violations(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    assert created["can_submit"] is False
    assert "Hosts are not set" in created["cannot_submit_reasons"]

    add_external_host(events_client, created["id"], user_headers)
    fill_locales(events_client, created["id"], user_headers)
    cleared_location = events_client.patch(
        f"/drafts/{created['id']}",
        json={"location": ""},
        headers=user_headers,
    )
    assert cleared_location.status_code == 200
    assert "Location is empty" in cleared_location.json()["cannot_submit_reasons"]

    restored_location = events_client.patch(
        f"/drafts/{created['id']}",
        json={"location": "108", "starts_at": past_iso()},
        headers=user_headers,
    )
    assert restored_location.status_code == 200
    payload = restored_location.json()
    assert payload["can_submit"] is False
    assert "Event start time in the past" in payload["cannot_submit_reasons"]


def test_can_submit_true_for_complete_draft(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    add_external_host(events_client, created["id"], user_headers)
    fill_locales(events_client, created["id"], user_headers)
    response = events_client.get(f"/drafts/{created['id']}", headers=user_headers)
    assert response.status_code == 200
    draft = response.json()
    assert draft["can_submit"] is True
    assert draft["cannot_submit_reasons"] == []


def test_can_submit_requires_duration_and_enrollment(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers, duration_hours=None, enrollment=None)
    add_external_host(events_client, created["id"], user_headers)
    fill_locales(events_client, created["id"], user_headers)
    draft = events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()
    assert "Event duration is not set" in draft["cannot_submit_reasons"]
    assert "Enrollment is not set" in draft["cannot_submit_reasons"]


def test_upload_image(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    response = events_client.post(
        f"/drafts/{created['id']}/image",
        files={"image_file": ("image.png", _white_png(), "image/png")},
        headers=user_headers,
    )
    assert response.status_code == 200
    image_id = response.json()["image_id"]
    draft = events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()
    assert draft["data"]["image_id"] == image_id

    invalid = events_client.post(
        f"/drafts/{created['id']}/image",
        files={"image_file": ("image.txt", b"not an image", "text/plain")},
        headers=user_headers,
    )
    assert invalid.status_code == 400


def test_draft_image_redirect(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    missing = events_client.get(f"/drafts/{created['id']}/image", follow_redirects=False)
    assert missing.status_code == 404

    upload = events_client.post(
        f"/drafts/{created['id']}/image",
        files={"image_file": ("image.png", _white_png(), "image/png")},
        headers=user_headers,
    )
    assert upload.status_code == 200
    image_id = upload.json()["image_id"]

    response = events_client.get(f"/drafts/{created['id']}/image", follow_redirects=False)
    assert response.status_code == 307
    assert image_id in response.headers["location"]


def test_restore_from_submission(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    add_external_host(events_client, created["id"], user_headers)
    fill_locales(events_client, created["id"], user_headers)
    submit(events_client, created["id"], user_headers)
    events_client.patch(f"/drafts/{created['id']}", json={"location": "changed"}, headers=user_headers)

    response = events_client.post(f"/drafts/{created['id']}/restore", json={"from": "submission"}, headers=user_headers)
    assert response.status_code == 200
    restored = response.json()
    assert restored["data"]["location"] == "108"
    assert restored["status"] == "pending"


def test_restore_from_public(events_client: TestClient, club_leader_headers, superadmin_headers):
    created = create_draft(events_client, club_leader_headers)
    add_club_host(events_client, created["id"], club_leader_headers)
    fill_locales(events_client, created["id"], club_leader_headers)
    submit(events_client, created["id"], club_leader_headers)
    events_client.post(f"/submissions/{created['id']}/approve", json={"feedback": ""}, headers=superadmin_headers)
    events_client.patch(f"/drafts/{created['id']}", json={"location": "changed"}, headers=club_leader_headers)

    response = events_client.post(
        f"/drafts/{created['id']}/restore", json={"from": "public"}, headers=club_leader_headers
    )
    assert response.status_code == 200
    assert response.json()["status"] == "published"


def test_delete_draft_blocked_when_published(events_client: TestClient, club_leader_headers, superadmin_headers):
    draft = create_and_publish(events_client, club_leader_headers, superadmin_headers, host="club")
    response = events_client.delete(f"/drafts/{draft['id']}", headers=club_leader_headers)
    assert response.status_code == 400
    assert "published" in response.json()["detail"]


def test_delete_draft_blocked_when_submission_pending(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    add_external_host(events_client, created["id"], user_headers)
    fill_locales(events_client, created["id"], user_headers)
    submit(events_client, created["id"], user_headers)
    response = events_client.delete(f"/drafts/{created['id']}", headers=user_headers)
    assert response.status_code == 400
    assert "pending" in response.json()["detail"]


def test_delete_draft_ok_when_no_submission(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    response = events_client.delete(f"/drafts/{created['id']}", headers=user_headers)
    assert response.status_code == 200
    assert events_client.get(f"/drafts/{created['id']}", headers=user_headers).status_code == 404


def test_delete_draft_ok_after_decline(events_client: TestClient, user_headers, superadmin_headers):
    created = create_draft(events_client, user_headers)
    add_external_host(events_client, created["id"], user_headers)
    fill_locales(events_client, created["id"], user_headers)
    submit(events_client, created["id"], user_headers)
    declined = events_client.post(
        f"/submissions/{created['id']}/decline",
        json={"feedback": "needs work"},
        headers=superadmin_headers,
    )
    assert declined.status_code == 200
    response = events_client.delete(f"/drafts/{created['id']}", headers=user_headers)
    assert response.status_code == 200


def test_draft_keeps_moderation_feedback_after_edit(events_client: TestClient, user_headers, superadmin_headers):
    created = create_draft(events_client, user_headers)
    add_external_host(events_client, created["id"], user_headers)
    fill_locales(events_client, created["id"], user_headers)
    submit(events_client, created["id"], user_headers)
    events_client.post(
        f"/submissions/{created['id']}/decline",
        json={"feedback": "needs work"},
        headers=superadmin_headers,
    )

    declined = events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()
    assert declined["status"] == "declined"
    assert declined["feedback"] == "needs work"

    events_client.patch(f"/drafts/{created['id']}", json={"location": "edited"}, headers=user_headers)
    edited = events_client.get(f"/drafts/{created['id']}", headers=user_headers).json()
    assert edited["status"] is None  # draft revision diverged from submission
    assert edited["feedback"] == "needs work"
