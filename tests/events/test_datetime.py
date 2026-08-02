from fastapi.testclient import TestClient

from tests.events.helpers import draft_payload, future_iso


def test_naive_datetime_rejected_on_create(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.post(
        "/drafts",
        json=draft_payload(starts_at="2026-07-30T19:00:00"),
        headers=user_headers,
    )
    assert response.status_code == 422
    assert "timezone-aware" in response.text


def test_offset_datetime_normalized_to_utc(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.post(
        "/drafts",
        json=draft_payload(starts_at="2026-07-30T19:00:00+03:00"),
        headers=user_headers,
    )
    assert response.status_code == 200
    draft = response.json()
    assert draft["data"]["starts_at"].endswith(("Z", "+00:00"))
    assert not draft["data"]["starts_at"].startswith("2026-07-30T19:00:00")


def test_utc_input_kept_as_utc(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.post(
        "/drafts",
        json=draft_payload(starts_at="2026-07-30T16:00:00Z"),
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.json()["data"]["starts_at"] == "2026-07-30T16:00:00Z"


def test_naive_datetime_rejected_in_query(events_client: TestClient):
    response = events_client.get("/events", params={"from": "2026-07-30T19:00:00"})
    assert response.status_code == 422


def test_invalid_datetime_rejected(events_client: TestClient, user_headers: dict[str, str]):
    response = events_client.post(
        "/drafts",
        json=draft_payload(starts_at="not-a-datetime"),
        headers=user_headers,
    )
    assert response.status_code == 422


def test_from_later_than_to_rejected(events_client: TestClient):
    response = events_client.get(
        "/events",
        params={"from": future_iso(30), "to": future_iso(1)},
    )
    assert response.status_code == 400
    assert "from must not be later than to" in response.json()["detail"]
