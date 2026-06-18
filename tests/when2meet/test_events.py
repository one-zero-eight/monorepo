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


def test_get_my_events(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify filtering events owned by the user."""
    when2meet_client.post(
        "/api/v0/events", json={"name": "My Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=user_headers
    )

    other_headers = auth_header_factory("other-user", "other@example.com")
    when2meet_client.post(
        "/api/v0/events", json={"name": "Other Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=other_headers
    )

    response = when2meet_client.get("/api/v0/events/mine", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "My Meeting"
    assert "participants_count" in data[0]


def test_get_participating_events(when2meet_client: TestClient, user_headers, auth_header_factory):
    """Verify filtering events where user is a participant but not owner."""
    other_headers = auth_header_factory("other-user", "other@example.com")

    create_resp = when2meet_client.post(
        "/api/v0/events", json={"name": "Other's Meeting", "slots": ["2026-06-15T10:00:00Z"]}, headers=other_headers
    )
    event_id = create_resp.json()["id"]

    when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"name": "Alice (test-user-1)", "availability": ["2026-06-15T10:00:00Z"]},
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
        json={"name": "Bob", "availability": ["2026-06-15T11:00:00Z"]},
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


def test_update_participant_full(when2meet_client: TestClient, user_headers):
    """Verify updating participant availability including if_needed status."""
    create_resp = when2meet_client.post(
        "/api/v0/events",
        json={"name": "If Needed Meeting", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]},
        headers=user_headers,
    )
    event_id = create_resp.json()["id"]

    part_data = {
        "name": "Charlie",
        "availability": ["2026-06-15T10:00:00Z"],
        "if_needed": ["2026-06-15T11:00:00Z"],
    }
    resp = when2meet_client.put(f"/api/v0/events/{event_id}/participants", json=part_data, headers=user_headers)
    assert resp.status_code == 200
    data = resp.json()
    part = data["participants"][0]
    assert part["availability"] == ["2026-06-15T10:00:00Z"]
    assert part["if_needed"] == ["2026-06-15T11:00:00Z"]

    part_data_overlap = {
        "name": "Charlie",
        "availability": ["2026-06-15T10:00:00Z"],
        "if_needed": ["2026-06-15T10:00:00Z"],
    }
    resp = when2meet_client.put(f"/api/v0/events/{event_id}/participants", json=part_data_overlap, headers=user_headers)
    assert resp.status_code == 400
    assert "cannot be both available and if_needed" in resp.json()["detail"]


def test_update_participant_invalid_slot(when2meet_client: TestClient, user_headers):
    """Verify that participants cannot pick slots outside the event grid."""
    event_data = {"name": "Slot Bound", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/events", json=event_data, headers=user_headers)
    event_id = create_response.json()["id"]

    participant_data = {"name": "Alice", "availability": ["2026-06-15T12:00:00Z"]}
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
        json={"name": "Other", "availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )

    del_resp = when2meet_client.delete(f"/api/v0/events/{event_id}/participants/Other", headers=user_headers)
    assert del_resp.status_code == 200
    assert len(del_resp.json()["participants"]) == 0

    when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"name": "Other", "availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )

    del_resp = when2meet_client.delete(f"/api/v0/events/{event_id}/participants/Other", headers=other_headers)
    assert del_resp.status_code == 200
    assert len(del_resp.json()["participants"]) == 0

    when2meet_client.put(
        f"/api/v0/events/{event_id}/participants",
        json={"name": "Other", "availability": ["2026-06-15T10:00:00Z"]},
        headers=other_headers,
    )
    random_headers = auth_header_factory("random-user", "random@example.com")
    del_resp = when2meet_client.delete(f"/api/v0/events/{event_id}/participants/Other", headers=random_headers)
    assert del_resp.status_code == 403


def test_search_events(when2meet_client: TestClient, user_headers):
    """Verify searching events by name or description."""
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
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Unique Searchable Name"

    resp = when2meet_client.get("/api/v0/events/?q=Description", headers=user_headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Common Name"


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
