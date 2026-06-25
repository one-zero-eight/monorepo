from starlette.testclient import TestClient


def test_create_event_with_auth(when2meet_client: TestClient, user_headers):
    """Verify event creation with ownership link."""
    event_data = {
        "name": "Auth Meeting",
        "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"],
    }
    response = when2meet_client.post("/api/v0/events", json=event_data, headers=user_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["owner_id"] == "test-user-1"


def test_get_event(when2meet_client: TestClient, user_headers):
    """Verify loading event details."""
    event_data = {"name": "Load Test", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/events", json=event_data, headers=user_headers)
    event_id = create_response.json()["id"]

    response = when2meet_client.get(f"/api/v0/events/{event_id}", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Load Test"


def test_get_event_by_slug(when2meet_client: TestClient, user_headers):
    """Verify loading event details by short slug."""
    event_data = {"name": "Slug Load Test", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/events", json=event_data, headers=user_headers)
    slug = create_response.json()["slug"]

    response = when2meet_client.get(f"/api/v0/events/{slug}", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Slug Load Test"
    assert response.json()["slug"] == slug


def test_get_my_events(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify filtering events owned by the user."""
    when2meet_client.post(
        "/api/v0/events", json={"name": "My Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )

    other_headers = auth_header_factory("other-user", "other@example.com")
    when2meet_client.post(
        "/api/v0/events", json={"name": "Other Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=other_headers
    )

    response = when2meet_client.get("/api/v0/events/", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "My Meeting"
    assert "slug" in data[0]
    assert "participants_count" in data[0]


def test_events_mine_removed(when2meet_client: TestClient, user_headers):
    """Verify legacy owned events endpoint is removed."""
    response = when2meet_client.get("/api/v0/events/mine", headers=user_headers)
    assert response.status_code == 404


def test_get_participating_events(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify filtering events where user is a participant but not owner."""
    other_headers = auth_header_factory("other-user", "other@example.com")

    create_resp = when2meet_client.post(
        "/api/v0/events", json={"name": "Other's Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=other_headers
    )
    event_id = create_resp.json()["id"]

    when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )

    response = when2meet_client.get("/api/v0/events/participating", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Other's Meeting"


def test_patch_event_owner(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify partial updates restricted to owner."""
    create_resp = when2meet_client.post(
        "/api/v0/events", json={"name": "Initial Name", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )
    event_id = create_resp.json()["id"]

    patch_resp = when2meet_client.patch(
        f"/api/v0/events/{event_id}", json={"name": "Updated Name"}, headers=user_headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated Name"

    other_headers = auth_header_factory("other-user", "other@example.com")
    patch_resp = when2meet_client.patch(
        f"/api/v0/events/{event_id}", json={"name": "Hacker Name"}, headers=other_headers
    )
    assert patch_resp.status_code == 403


def test_patch_event_invalid_slots(when2meet_client: TestClient, user_headers):
    """Verify that removing active slots is blocked."""
    create_resp = when2meet_client.post(
        "/api/v0/events",
        json={"name": "Slot Meeting", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"availability": ["2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )

    patch_resp = when2meet_client.patch(
        f"/api/v0/events/{event_id}", json={"slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )
    assert patch_resp.status_code == 400
    assert "not in the new slots" in patch_resp.json()["detail"]


def test_delete_event(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify event deletion restricted to owner."""
    create_resp = when2meet_client.post(
        "/api/v0/events", json={"name": "Delete Me", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )
    event_id = create_resp.json()["id"]

    other_headers = auth_header_factory("other-user", "other@example.com")
    del_resp = when2meet_client.delete(f"/api/v0/events/{event_id}", headers=other_headers)
    assert del_resp.status_code == 403

    del_resp = when2meet_client.delete(f"/api/v0/events/{event_id}", headers=user_headers)
    assert del_resp.status_code == 204

    get_resp = when2meet_client.get(f"/api/v0/events/{event_id}", headers=user_headers)
    assert get_resp.status_code == 404


def test_update_participant_upserts_by_authenticated_user(when2meet_client: TestClient, user_headers):
    """Verify participant availability is tied to the authenticated user."""
    create_resp = when2meet_client.post(
        "/api/v0/events",
        json={"name": "Participant Meeting", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    part_data = {"availability": ["2026-06-15T10:00:00Z"]}
    resp = when2meet_client.put(f"/api/v0/events/{event_id}/participants", json=part_data, headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    part = data["participants"][0]
    assert part["user_id"] == "test-user-1"
    assert part["email"] == "test-user-1@innopolis.university"
    assert part["first_name"] == "Test"
    assert part["last_name"] == "One"
    assert part["telegram"] == "@test_user_one"
    assert part["availability"] == ["2026-06-15T10:00:00Z"]

    get_resp = when2meet_client.get(f"/api/v0/events/{event_id}", headers=user_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["participants"][0]["email"] == "test-user-1@innopolis.university"

    resp = when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
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
        "/api/v0/events",
        json={"name": "Missing Profile", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]
    other_headers = auth_header_factory("other-user", "other@example.com")

    response = when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )
    assert response.status_code == 200
    participant = response.json()["participants"][0]
    assert participant["user_id"] == "other-user"
    assert participant["email"] is None
    assert participant["first_name"] is None
    assert participant["last_name"] is None
    assert participant["telegram"] is None
    assert participant["availability"] == ["2026-06-15T10:00:00Z"]


def test_update_participant_rejects_extra_fields(when2meet_client: TestClient, user_headers):
    """Verify participant body does not accept user_id, name, or if_needed."""
    create_resp = when2meet_client.post(
        "/api/v0/events",
        json={"name": "Participant Body", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    resp = when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={
            "user_id": "other-user",
            "name": "Legacy Name",
            "availability": ["2026-06-15T10:00:00Z"],
            "if_needed": ["2026-06-15T10:00:00Z"],
        },
        headers=user_headers,
    )
    assert resp.status_code == 422


def test_update_participant_invalid_slot(when2meet_client: TestClient, user_headers):
    """Verify that participants cannot pick slots outside the event grid."""
    event_data = {"name": "Slot Bound", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/events", json=event_data, headers=user_headers)
    event_id = create_response.json()["id"]

    participant_data = {"availability": ["2026-06-15T12:00:00Z"]}
    response = when2meet_client.put(
        f"/api/v0/events/{event_id}/participants", json=participant_data, headers=user_headers
    )
    assert response.status_code == 400
    assert "not available for this event" in response.json()["detail"]


def test_delete_participant(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify participant deletion by owner or participant themselves."""
    create_resp = when2meet_client.post(
        "/api/v0/events", json={"name": "Participant Admin", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )
    event_id = create_resp.json()["id"]

    other_headers = auth_header_factory("other-user", "other@example.com")
    when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )

    del_resp = when2meet_client.delete(f"/api/v0/events/{event_id}/participants/other-user", headers=user_headers)
    assert del_resp.status_code == 200
    assert len(del_resp.json()["participants"]) == 0

    when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )

    del_resp = when2meet_client.delete(f"/api/v0/events/{event_id}/participants/other-user", headers=other_headers)
    assert del_resp.status_code == 200
    assert len(del_resp.json()["participants"]) == 0

    when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )
    random_headers = auth_header_factory("random-user", "random@example.com")
    del_resp = when2meet_client.delete(f"/api/v0/events/{event_id}/participants/other-user", headers=random_headers)
    assert del_resp.status_code == 403


def test_events_query_param_does_not_search(when2meet_client: TestClient, user_headers):
    """Verify GET /events/ ignores search params and returns owned events."""
    when2meet_client.post(
        "/api/v0/events",
        json={"name": "Unique Searchable Name", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )
    when2meet_client.post(
        "/api/v0/events",
        json={"name": "Common Name", "description": "Searchable Description", "slots": ["2026-06-15T10:00:00Z"]},
        headers=user_headers,
    )

    resp = when2meet_client.get("/api/v0/events/?q=Unique", headers=user_headers)
    assert resp.status_code == 200
    assert {event["name"] for event in resp.json()} == {"Unique Searchable Name", "Common Name"}


def test_slot_normalization_and_sorting(when2meet_client: TestClient, user_headers):
    """Verify backend ensures consistent slot format and order."""
    event_data = {
        "name": "Normalization",
        "slots": ["2026-06-15T11:00:00.123Z", "2026-06-15T10:00:00Z"],
    }
    response = when2meet_client.post("/api/v0/events", json=event_data, headers=user_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["slots"] == ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]
