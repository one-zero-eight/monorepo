import httpx
import pytest
import respx
from beanie import PydanticObjectId
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.when2meet.modules.events import events_repo, routes

ROOM_BOOKING_API_URL = "https://room-booking.test/api/v0"


def _booking(room_id: str, start: str, end: str) -> dict:
    return {
        "room_id": room_id,
        "title": "Busy",
        "start": start,
        "end": end,
        "outlook_booking_id": None,
        "outlook_entry_id": "busy-1",
        "attendees": None,
    }


def test_room_booking_get_requires_config(when2meet_client: TestClient, monkeypatch):
    """Verify room-booking HTTP helper validates integration config."""
    monkeypatch.setattr(routes.settings, "room_booking", None)
    portal = when2meet_client.portal
    assert portal is not None

    with pytest.raises(HTTPException) as exc_info:
        portal.call(routes._room_booking_get, "/rooms/", {}, "Bearer user-token")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Room Booking integration is not configured"


def test_room_booking_get_network_failure_returns_bad_gateway(when2meet_client: TestClient):
    """Verify room-booking network errors are hidden behind a stable API error."""
    portal = when2meet_client.portal
    assert portal is not None

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get(f"{ROOM_BOOKING_API_URL}/rooms/").mock(side_effect=httpx.ConnectError("boom"))

        with pytest.raises(HTTPException) as exc_info:
            portal.call(routes._room_booking_get, "/rooms/", {}, "Bearer user-token")

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Failed to call Room Booking API"


def test_create_event_with_auth(when2meet_client: TestClient, user_headers):
    """Verify event creation with ownership link."""
    event_data = {
        "name": "Auth Meeting",
        "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"],
    }
    response = when2meet_client.post("/api/v0/meetings", json=event_data, headers=user_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["owner_id"] == "test-user-1"


def test_get_event(when2meet_client: TestClient, user_headers):
    """Verify loading event details."""
    event_data = {"name": "Load Test", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/meetings", json=event_data, headers=user_headers)
    event_id = create_response.json()["id"]

    response = when2meet_client.get(f"/api/v0/meetings/{event_id}", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Load Test"


def test_get_event_by_slug(when2meet_client: TestClient, user_headers):
    """Verify loading event details by short slug."""
    event_data = {"name": "Slug Load Test", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/meetings", json=event_data, headers=user_headers)
    slug = create_response.json()["slug"]

    response = when2meet_client.get(f"/api/v0/meetings/{slug}", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Slug Load Test"
    assert response.json()["slug"] == slug


def test_events_repo_read_returns_event_by_id(when2meet_client: TestClient, user_headers):
    """Verify repository read returns an existing event."""
    event_data = {"name": "Repo Read Test", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/meetings", json=event_data, headers=user_headers)
    event_id = PydanticObjectId(create_response.json()["id"])

    portal = when2meet_client.portal
    assert portal is not None

    event = portal.call(events_repo.read, event_id)

    assert event is not None
    assert event.name == "Repo Read Test"


def test_get_event_not_found(when2meet_client: TestClient, user_headers):
    """Verify unknown event references return the public 404 contract."""
    response = when2meet_client.get("/api/v0/meetings/missing-event", headers=user_headers)

    assert response.status_code == 404
    assert response.json()["detail"] == "Meeting not found"


def test_get_my_events(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify filtering events owned by the user."""
    when2meet_client.post(
        "/api/v0/meetings", json={"name": "My Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )

    other_headers = auth_header_factory("other-user", "other@example.com")
    when2meet_client.post(
        "/api/v0/meetings", json={"name": "Other Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=other_headers
    )

    response = when2meet_client.get("/api/v0/meetings/", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "My Meeting"
    assert "slug" in data[0]
    assert "participants_count" in data[0]


def test_events_mine_removed(when2meet_client: TestClient, user_headers):
    """Verify legacy owned events endpoint is removed."""
    response = when2meet_client.get("/api/v0/meetings/mine", headers=user_headers)
    assert response.status_code == 404


def test_get_participating_events(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify filtering events where user is a participant but not owner."""
    other_headers = auth_header_factory("other-user", "other@example.com")

    create_resp = when2meet_client.post(
        "/api/v0/meetings", json={"name": "Other's Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=other_headers
    )
    event_id = create_resp.json()["id"]

    when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )

    response = when2meet_client.get("/api/v0/meetings/participating", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Other's Meeting"


def test_patch_event_owner(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify partial updates restricted to owner."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings", json={"name": "Initial Name", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )
    event_id = create_resp.json()["id"]

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}", json={"name": "Updated Name"}, headers=user_headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Name"

    other_headers = auth_header_factory("other-user", "other@example.com")
    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}", json={"name": "Hacker Name"}, headers=other_headers
    )
    assert patch_resp.status_code == 403


def test_owner_selects_meeting_time_visible_to_participants(
    when2meet_client: TestClient,
    user_headers,
    auth_header_factory,
):
    """Verify owner can store final meeting time and participants can read it."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Decision Time", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]
    selected_time = {"start": "2026-06-15T10:00:00.123Z", "end": "2026-06-15T11:00:00Z"}

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}",
        json={"selected_time": selected_time},
        headers=user_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["selected_time"] == {
        "start": "2026-06-15T10:00:00Z",
        "end": "2026-06-15T11:00:00Z",
    }

    other_headers = auth_header_factory("participant-user", "participant@example.com")
    get_resp = when2meet_client.get(f"/api/v0/meetings/{event_id}", headers=other_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["selected_time"] == {
        "start": "2026-06-15T10:00:00Z",
        "end": "2026-06-15T11:00:00Z",
    }

    summary_resp = when2meet_client.get("/api/v0/meetings/", headers=user_headers)
    assert summary_resp.status_code == 200
    assert summary_resp.json()[0]["selected_time"] == {
        "start": "2026-06-15T10:00:00Z",
        "end": "2026-06-15T11:00:00Z",
    }


def test_non_owner_cannot_select_meeting_time(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify selected meeting time is owner-controlled metadata."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Owner Time", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]
    other_headers = auth_header_factory("other-user", "other@example.com")

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}",
        json={"selected_time": {"start": "2026-06-15T10:00:00Z", "end": "2026-06-15T11:00:00Z"}},
        headers=other_headers,
    )

    assert patch_resp.status_code == 403


def test_selected_meeting_time_requires_end_after_start(when2meet_client: TestClient, user_headers):
    """Verify invalid selected meeting intervals are rejected."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Invalid Time", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}",
        json={"selected_time": {"start": "2026-06-15T11:00:00Z", "end": "2026-06-15T10:00:00Z"}},
        headers=user_headers,
    )

    assert patch_resp.status_code == 422


def test_available_rooms_requires_selected_meeting_time(when2meet_client: TestClient, user_headers):
    """Verify available rooms cannot be requested before meeting time is selected."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "No Time Rooms", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    response = when2meet_client.get(f"/api/v0/meetings/{event_id}/available-rooms", headers=user_headers)

    assert response.status_code == 400
    assert response.json()["detail"] == "Selected meeting time is not set"


def test_available_rooms_returns_only_rooms_free_for_full_selected_time(
    when2meet_client: TestClient,
    user_headers,
):
    """Verify rooms with overlapping bookings are excluded from availability."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Room Search", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]
    selected_time = {"start": "2026-06-15T10:00:00Z", "end": "2026-06-15T11:00:00Z"}
    when2meet_client.patch(f"/api/v0/meetings/{event_id}", json={"selected_time": selected_time}, headers=user_headers)

    with respx.mock(assert_all_called=True) as respx_mock:
        rooms_route = respx_mock.get(f"{ROOM_BOOKING_API_URL}/rooms/").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"id": "3.1", "title": "Meeting Room 3.1", "short_name": "3.1", "capacity": 8},
                    {"id": "3.2", "title": "Meeting Room 3.2", "short_name": "3.2", "capacity": 12},
                    {"id": "3.3", "title": "Meeting Room 3.3", "short_name": "3.3", "capacity": 10},
                    {"id": "107", "title": "Red Room 107", "short_name": "107", "capacity": 40},
                ],
            )
        )
        bookings_route = respx_mock.get(f"{ROOM_BOOKING_API_URL}/bookings/").mock(
            return_value=httpx.Response(
                200,
                json=[
                    _booking("3.1", "2026-06-15T10:30:00Z", "2026-06-15T11:30:00Z"),
                    _booking("3.2", "2026-06-15T09:00:00Z", "2026-06-15T10:00:00Z"),
                    _booking("3.3", "2026-06-15T11:00:00Z", "2026-06-15T12:00:00Z"),
                ],
            )
        )
        can_book_3_2_route = respx_mock.get(f"{ROOM_BOOKING_API_URL}/room/3.2/can-book").mock(
            return_value=httpx.Response(200, json={"can_book": True, "reason_why_cannot": ""})
        )
        can_book_3_3_route = respx_mock.get(f"{ROOM_BOOKING_API_URL}/room/3.3/can-book").mock(
            return_value=httpx.Response(200, json={"can_book": False, "reason_why_cannot": "No access"})
        )
        can_book_107_route = respx_mock.get(f"{ROOM_BOOKING_API_URL}/room/107/can-book").mock(
            return_value=httpx.Response(200, json={"can_book": True, "reason_why_cannot": ""})
        )

        response = when2meet_client.get(f"/api/v0/meetings/{event_id}/available-rooms", headers=user_headers)

    assert rooms_route.calls.last is not None
    assert rooms_route.calls.last.request.headers["Authorization"] == user_headers["Authorization"]
    assert rooms_route.calls.last.request.url.params["include_red"] == "true"

    assert bookings_route.calls.last is not None
    bookings_request = bookings_route.calls.last.request
    assert bookings_request.headers["Authorization"] == user_headers["Authorization"]
    assert bookings_request.url.params.get_list("room_ids") == ["3.1", "3.2", "3.3", "107"]
    assert bookings_request.url.params["start"] == "2026-06-15T10:00:00+00:00"
    assert bookings_request.url.params["end"] == "2026-06-15T11:00:00+00:00"

    for route in (can_book_3_2_route, can_book_3_3_route, can_book_107_route):
        assert route.calls.last is not None
        can_book_request = route.calls.last.request
        assert can_book_request.headers["Authorization"] == user_headers["Authorization"]
        assert can_book_request.url.params["start"] == "2026-06-15T10:00:00+00:00"
        assert can_book_request.url.params["end"] == "2026-06-15T11:00:00+00:00"

    assert response.status_code == 200
    room_by_id = {room["id"]: room for room in response.json()}
    assert "3.1" not in room_by_id
    assert room_by_id["3.2"] == {
        "id": "3.2",
        "name": "Meeting Room 3.2",
        "capacity": 12,
        "location": "3.2",
    }
    assert "3.3" not in room_by_id
    assert room_by_id["107"] == {
        "id": "107",
        "name": "Red Room 107",
        "capacity": 40,
        "location": "107",
    }


def test_available_rooms_returns_bad_gateway_when_room_booking_fails(
    when2meet_client: TestClient,
    user_headers,
):
    """Verify room-booking upstream errors are hidden behind a stable API error."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Room Search Failure", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]
    selected_time = {"start": "2026-06-15T10:00:00Z", "end": "2026-06-15T11:00:00Z"}
    when2meet_client.patch(f"/api/v0/meetings/{event_id}", json={"selected_time": selected_time}, headers=user_headers)

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get(f"{ROOM_BOOKING_API_URL}/rooms/").mock(return_value=httpx.Response(503))
        response = when2meet_client.get(f"/api/v0/meetings/{event_id}/available-rooms", headers=user_headers)

    assert response.status_code == 502
    assert response.json()["detail"] == "Room Booking API returned an error"


def test_patch_event_not_found(when2meet_client: TestClient, user_headers):
    """Verify updating an unknown event keeps the API contract stable."""
    patch_resp = when2meet_client.patch(
        "/api/v0/meetings/missing-event",
        json={"name": "Updated Name"},
        headers=user_headers,
    )

    assert patch_resp.status_code == 404
    assert patch_resp.json()["detail"] == "Meeting not found"


def test_patch_event_preserves_hidden_participant_slots(when2meet_client: TestClient, user_headers):
    """Verify removed event slots stay in participant availability."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Slot Meeting", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}", json={"slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["participants"][0]["availability"] == ["2026-06-15T11:00:00Z"]

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}",
        json={"slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["participants"][0]["availability"] == ["2026-06-15T11:00:00Z"]


def test_update_participant_keeps_hidden_slots(when2meet_client: TestClient, user_headers):
    """Verify editing availability does not discard slots hidden by the organizer."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={
            "name": "Hidden Slot Meeting",
            "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z", "2026-06-15T12:00:00Z"],
        },
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}",
        json={"slots": ["2026-06-15T10:00:00Z", "2026-06-15T12:00:00Z"]},
        headers=user_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["participants"][0]["availability"] == ["2026-06-15T11:00:00Z"]

    update_resp = when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T12:00:00Z"]},
        headers=user_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["participants"][0]["availability"] == [
        "2026-06-15T11:00:00Z",
        "2026-06-15T12:00:00Z",
    ]

    patch_resp = when2meet_client.patch(
        f"/api/v0/meetings/{event_id}",
        json={
            "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z", "2026-06-15T12:00:00Z"],
        },
        headers=user_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["participants"][0]["availability"] == [
        "2026-06-15T11:00:00Z",
        "2026-06-15T12:00:00Z",
    ]


def test_update_participant_deduplicates_hidden_slots_from_full_payload(when2meet_client: TestClient, user_headers):
    """Verify full frontend payloads do not duplicate previously hidden slots."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={
            "name": "Full Payload Meeting",
            "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z", "2026-06-15T12:00:00Z"],
        },
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    when2meet_client.patch(
        f"/api/v0/meetings/{event_id}",
        json={"slots": ["2026-06-15T10:00:00Z", "2026-06-15T12:00:00Z"]},
        headers=user_headers,
    )

    update_resp = when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T11:00:00Z", "2026-06-15T12:00:00Z"]},
        headers=user_headers,
    )

    assert update_resp.status_code == 200
    assert update_resp.json()["participants"][0]["availability"] == [
        "2026-06-15T11:00:00Z",
        "2026-06-15T12:00:00Z",
    ]


def test_delete_event(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify event deletion restricted to owner."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings", json={"name": "Delete Me", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )
    event_id = create_resp.json()["id"]

    other_headers = auth_header_factory("other-user", "other@example.com")
    del_resp = when2meet_client.delete(f"/api/v0/meetings/{event_id}", headers=other_headers)
    assert del_resp.status_code == 403

    del_resp = when2meet_client.delete(f"/api/v0/meetings/{event_id}", headers=user_headers)
    assert del_resp.status_code == 204

    get_resp = when2meet_client.get(f"/api/v0/meetings/{event_id}", headers=user_headers)
    assert get_resp.status_code == 404


def test_update_participant_upserts_by_authenticated_user(when2meet_client: TestClient, user_headers):
    """Verify participant availability is tied to the authenticated user."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Participant Meeting", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    part_data = {"availability": ["2026-06-15T10:00:00Z"]}
    resp = when2meet_client.put(f"/api/v0/meetings/{event_id}/participants", json=part_data, headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    part = data["participants"][0]
    assert part["user_id"] == "test-user-1"
    assert part["email"] == "test-user-1@innopolis.university"
    assert part["name"] == "Test User One"
    assert part["telegram"] == "@test_user_one"
    assert part["availability"] == ["2026-06-15T10:00:00Z"]

    get_resp = when2meet_client.get(f"/api/v0/meetings/{event_id}", headers=user_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["participants"][0]["email"] == "test-user-1@innopolis.university"

    resp = when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["participants"]) == 1
    assert data["participants"][0]["availability"] == ["2026-06-15T11:00:00Z"]


def test_participant_profile_fallback_when_accounts_user_missing(
    when2meet_client: TestClient,
    user_headers,
    auth_header_factory,
):
    """Verify missing Accounts profile keeps participant availability visible."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Missing Profile", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]
    other_headers = auth_header_factory("other-user", "other@example.com")

    response = when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )
    assert response.status_code == 200
    participant = response.json()["participants"][0]
    assert participant["user_id"] == "other-user"
    assert participant["email"] is None
    assert participant["name"] is None
    assert participant["telegram"] is None
    assert participant["availability"] == ["2026-06-15T10:00:00Z"]


def test_participant_profile_fallback_when_accounts_enrichment_fails(
    when2meet_client: TestClient,
    user_headers,
    monkeypatch,
):
    """Verify Accounts failures do not hide participant availability."""
    from src.when2meet.modules.events import routes

    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Accounts Failure", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )

    async def fail_get_users(user_ids: list[str]):
        raise ValueError("Accounts unavailable")

    monkeypatch.setattr(routes.inh_accounts, "get_users", fail_get_users)

    response = when2meet_client.get(f"/api/v0/meetings/{event_id}", headers=user_headers)

    assert response.status_code == 200
    participant = response.json()["participants"][0]
    assert participant["user_id"] == "test-user-1"
    assert participant["email"] is None
    assert participant["name"] is None
    assert participant["telegram"] is None
    assert participant["availability"] == ["2026-06-15T10:00:00Z"]


def test_update_participant_rejects_extra_fields(when2meet_client: TestClient, user_headers):
    """Verify participant body does not accept user_id, name, or if_needed."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Participant Body", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    resp = when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={
            "user_id": "other-user",
            "name": "Legacy Name",
            "availability": ["2026-06-15T10:00:00Z"],
            "if_needed": ["2026-06-15T10:00:00Z"],
        },
        headers=user_headers,
    )
    assert resp.status_code == 422


def test_update_participant_accepts_slots_outside_current_event_grid(when2meet_client: TestClient, user_headers):
    """Verify participants can save slots outside the current event grid."""
    event_data = {"name": "Slot Bound", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/meetings", json=event_data, headers=user_headers)
    event_id = create_response.json()["id"]

    participant_data = {"availability": ["2026-06-15T12:00:00Z"]}
    response = when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants", json=participant_data, headers=user_headers
    )
    assert response.status_code == 200
    assert response.json()["participants"][0]["availability"] == ["2026-06-15T12:00:00Z"]


def test_update_participant_event_not_found(when2meet_client: TestClient, user_headers):
    """Verify participant updates fail clearly for unknown event references."""
    response = when2meet_client.put(
        "/api/v0/meetings/missing-event/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Meeting not found"


def test_delete_participant(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify participant deletion by owner or participant themselves."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings", json={"name": "Participant Admin", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )
    event_id = create_resp.json()["id"]

    other_headers = auth_header_factory("other-user", "other@example.com")
    when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )

    del_resp = when2meet_client.delete(f"/api/v0/meetings/{event_id}/participants/other-user", headers=user_headers)
    assert del_resp.status_code == 200
    assert len(del_resp.json()["participants"]) == 0

    when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )

    del_resp = when2meet_client.delete(f"/api/v0/meetings/{event_id}/participants/other-user", headers=other_headers)
    assert del_resp.status_code == 200
    assert len(del_resp.json()["participants"]) == 0

    when2meet_client.put(
        f"/api/v0/meetings/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )
    random_headers = auth_header_factory("random-user", "random@example.com")
    del_resp = when2meet_client.delete(f"/api/v0/meetings/{event_id}/participants/other-user", headers=random_headers)
    assert del_resp.status_code == 403


def test_delete_participant_not_found(when2meet_client: TestClient, user_headers):
    """Verify participant deletion distinguishes missing participant from missing event."""
    create_resp = when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Participant Missing", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    del_resp = when2meet_client.delete(f"/api/v0/meetings/{event_id}/participants/missing-user", headers=user_headers)

    assert del_resp.status_code == 404
    assert del_resp.json()["detail"] == "Participant not found"


def test_events_query_param_does_not_search(when2meet_client: TestClient, user_headers):
    """Verify GET /meetings/ ignores search params and returns owned events."""
    when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Unique Searchable Name", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    when2meet_client.post(
        "/api/v0/meetings",
        json={"name": "Common Name", "description": "Searchable Description", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )

    resp = when2meet_client.get("/api/v0/meetings/?q=Unique", headers=user_headers)
    assert resp.status_code == 200
    assert {event["name"] for event in resp.json()} == {"Unique Searchable Name", "Common Name"}


def test_slot_normalization_and_sorting(when2meet_client: TestClient, user_headers):
    """Verify backend ensures consistent slot format and order."""
    event_data = {
        "name": "Normalization",
        "slots": ["2026-06-15T11:00:00.123Z", "2026-06-15T10:00:00Z"],
    }
    response = when2meet_client.post("/api/v0/meetings", json=event_data, headers=user_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["slots"] == ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]
