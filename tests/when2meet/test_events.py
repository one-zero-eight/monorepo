from fastapi.testclient import TestClient


def test_create_event(when2meet_client: TestClient):
    event_data = {
        "name": "Team Meeting",
        "description": "Discuss project progress",
        "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"],
    }
    response = when2meet_client.post("/api/v0/events", json=event_data)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Team Meeting"
    assert "id" in data
    assert len(data["slots"]) == 2


def test_update_participant_invalid_slot(when2meet_client: TestClient):
    event_data = {"name": "Team Meeting", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/events", json=event_data)
    event_id = create_response.json()["id"]

    participant_data = {"name": "Alice", "availability": ["2026-06-15T12:00:00Z"]}
    response = when2meet_client.put(f"/api/v0/events/{event_id}/participants", json=participant_data)
    assert response.status_code == 400
    assert "not available for this event" in response.json()["detail"]


def test_get_event(when2meet_client: TestClient):
    event_data = {"name": "Team Meeting", "slots": ["2026-06-15T10:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/events", json=event_data)
    event_id = create_response.json()["id"]

    response = when2meet_client.get(f"/api/v0/events/{event_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Team Meeting"


def test_update_participant(when2meet_client: TestClient):
    event_data = {"name": "Team Meeting", "slots": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]}
    create_response = when2meet_client.post("/api/v0/events", json=event_data)
    event_id = create_response.json()["id"]

    participant_data = {"name": "Alice", "availability": ["2026-06-15T10:00:00Z"]}
    response = when2meet_client.put(f"/api/v0/events/{event_id}/participants", json=participant_data)
    assert response.status_code == 200
    data = response.json()
    assert len(data["participants"]) == 1
    assert data["participants"][0]["name"] == "Alice"
    assert len(data["participants"][0]["availability"]) == 1

    updated_data = {"name": "Alice", "availability": ["2026-06-15T10:00:00Z", "2026-06-15T11:00:00Z"]}
    response = when2meet_client.put(f"/api/v0/events/{event_id}/participants", json=updated_data)
    assert response.status_code == 200
    data = response.json()
    assert len(data["participants"]) == 1
    assert len(data["participants"][0]["availability"]) == 2
