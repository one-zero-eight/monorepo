from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from tests.events.conftest import CLUB_ID
from tests.events.helpers import (
    club_host_payload,
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


def test_create_draft_as_club_leader_with_club_host(events_client: TestClient, club_leader_headers: dict[str, str]):
    response = events_client.post("/drafts", json=club_host_payload(), headers=club_leader_headers)
    assert response.status_code == 200
    draft = response.json()
    assert draft["creator_id"] == "club-leader-1"
    assert draft["status"] is None
    assert draft["data"]["host"] == {"type": "club", "club_id": CLUB_ID, "name": None, "url": None}
    assert set(draft["data"]["locales"]) == {"en", "ru"}


def test_create_draft_as_event_manager_with_external_host(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.post("/drafts", json=draft_payload(), headers=user_headers)
    assert response.status_code == 200
    assert response.json()["data"]["host"] == {
        "type": "external",
        "club_id": None,
        "name": "One Zero Eight",
        "url": None,
    }


def test_club_host_requires_ownership(events_client: TestClient, user_headers: dict[str, str]):
    # user_headers (test-user-1) is an event manager but owns no clubs.
    response = events_client.post("/drafts", json=club_host_payload(), headers=user_headers)
    assert response.status_code == 400
    assert "Only club leaders can use a club as a host" in response.json()["detail"]


def test_club_host_must_be_owned_club(events_client: TestClient, club_leader_headers: dict[str, str]):
    response = events_client.post(
        "/drafts",
        json=club_host_payload(host={"type": "club", "club_id": "64b7de000000000000000999"}),
        headers=club_leader_headers,
    )
    assert response.status_code == 400
    assert "not a leader" in response.json()["detail"]


def test_external_host_forbidden_for_club_leader(events_client: TestClient, club_leader_headers: dict[str, str]):
    # club-leader-1 is not an event manager (email not in the manager list).
    response = events_client.post("/drafts", json=draft_payload(), headers=club_leader_headers)
    assert response.status_code == 400
    assert "Only event managers can use an external host" in response.json()["detail"]


def test_create_draft_rejects_unknown_locale(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.post("/drafts", json=draft_payload(locales=["de"]), headers=user_headers)
    assert response.status_code == 400
    assert "not in the allowed list" in response.json()["detail"]


def test_drafts_are_private_to_author(events_client: TestClient, club_leader_headers, plain_user_headers):
    created = events_client.post("/drafts", json=club_host_payload(), headers=club_leader_headers).json()
    missing = events_client.get(f"/drafts/{created['id']}", headers=plain_user_headers)
    assert missing.status_code == 404
    own = events_client.get(f"/drafts/{created['id']}", headers=club_leader_headers)
    assert own.status_code == 200


def test_list_drafts_shows_only_own(events_client: TestClient, club_leader_headers, user_headers):
    events_client.post("/drafts", json=club_host_payload(), headers=club_leader_headers)
    events_client.post("/drafts", json=draft_payload(), headers=user_headers)

    leader_drafts = events_client.get("/drafts", headers=club_leader_headers).json()
    manager_drafts = events_client.get("/drafts", headers=user_headers).json()
    assert len(leader_drafts) == 1
    assert len(manager_drafts) == 1
    # descriptions are omitted in list responses
    assert all(locale.get("description") is None for d in manager_drafts for locale in d["data"]["locales"].values())


def test_patch_draft_data(events_client: TestClient, club_leader_headers: dict[str, str]):
    created = create_draft(events_client, club_leader_headers, host={"type": "club", "club_id": CLUB_ID})
    response = events_client.patch(
        f"/drafts/{created['id']}",
        json={"starts_at": future_iso(14), "location": "109"},
        headers=club_leader_headers,
    )
    assert response.status_code == 200
    draft = response.json()
    assert draft["data"]["location"] == "109"
    assert draft["revision"] != created["revision"]


def test_patch_host_validated(events_client: TestClient, club_leader_headers: dict[str, str]):
    created = create_draft(events_client, club_leader_headers, host={"type": "club", "club_id": CLUB_ID})
    response = events_client.patch(
        f"/drafts/{created['id']}",
        json={"host": {"type": "club", "club_id": "64b7de000000000000000999"}},
        headers=club_leader_headers,
    )
    assert response.status_code == 400
    assert "not a leader" in response.json()["detail"]


def test_patch_host_to_external_forbidden_for_club_leader(
    events_client: TestClient, club_leader_headers: dict[str, str]
):
    created = create_draft(events_client, club_leader_headers, host={"type": "club", "club_id": CLUB_ID})
    response = events_client.patch(
        f"/drafts/{created['id']}",
        json={"host": {"type": "external", "name": "Other"}},
        headers=club_leader_headers,
    )
    assert response.status_code == 400


def test_patch_locale_autocreates_and_validates(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers, locales=["en"])
    response = events_client.patch(
        f"/drafts/{created['id']}/locales/ru",
        json={"name": "Событие"},
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["locales"]["ru"] == {"name": "Событие", "description": None}

    invalid = events_client.patch(
        f"/drafts/{created['id']}/locales/de",
        json={"name": "x"},
        headers=user_headers,
    )
    assert invalid.status_code == 400


def test_delete_locale(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers, locales=["en", "ru"])
    response = events_client.delete(f"/drafts/{created['id']}/locales/ru", headers=user_headers)
    assert response.status_code == 200
    assert "ru" not in response.json()["data"]["locales"]


def test_eligible_reports_guardrail_violations(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)  # locales empty, host set
    response = events_client.post(f"/drafts/{created['id']}/eligible", headers=user_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["eligible"] is False
    assert "Event start time" not in "".join(payload["why"])  # starts_at is set and in the future

    fill_locales(events_client, created["id"], user_headers)
    past = events_client.patch(
        f"/drafts/{created['id']}",
        json={"starts_at": past_iso()},
        headers=user_headers,
    )
    assert past.status_code == 200
    response = events_client.post(f"/drafts/{created['id']}/eligible", headers=user_headers)
    payload = response.json()
    assert payload["eligible"] is False
    assert "Event start time in the past" in payload["why"]


def test_eligible_true_for_complete_draft(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    fill_locales(events_client, created["id"], user_headers)
    response = events_client.post(f"/drafts/{created['id']}/eligible", headers=user_headers)
    assert response.status_code == 200
    assert response.json() == {"eligible": True, "why": []}


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


def test_restore_from_submission(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
    fill_locales(events_client, created["id"], user_headers)
    submit(events_client, created["id"], user_headers)
    # change the draft afterwards
    events_client.patch(f"/drafts/{created['id']}", json={"location": "changed"}, headers=user_headers)

    response = events_client.post(f"/drafts/{created['id']}/restore", json={"from": "submission"}, headers=user_headers)
    assert response.status_code == 200
    restored = response.json()
    assert restored["data"]["location"] == "108"
    assert restored["status"] == "pending"


def test_restore_from_public(events_client: TestClient, club_leader_headers, superadmin_headers):
    created = create_draft(events_client, club_leader_headers, host={"type": "club", "club_id": CLUB_ID})
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
    draft = create_and_publish(
        events_client, club_leader_headers, superadmin_headers, host={"type": "club", "club_id": CLUB_ID}
    )
    response = events_client.delete(f"/drafts/{draft['id']}", headers=club_leader_headers)
    assert response.status_code == 400
    assert "published" in response.json()["detail"]


def test_delete_draft_blocked_when_submission_pending(events_client: TestClient, user_headers: dict[str, str]):
    created = create_draft(events_client, user_headers)
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
