"""Test helpers for the Events service."""

import datetime as dtm

from fastapi.testclient import TestClient

from tests.events.conftest import CLUB_ID


def future_iso(days: int = 7) -> str:
    return (dtm.datetime.now(dtm.UTC) + dtm.timedelta(days=days)).isoformat()


def past_iso() -> str:
    return (dtm.datetime.now(dtm.UTC) - dtm.timedelta(days=1)).isoformat()


def draft_payload(**overrides) -> dict:
    payload: dict = {
        "starts_at": future_iso(),
        "location": "108",
        "locales": ["en", "ru"],
        "host": {"type": "external", "name": "One Zero Eight"},
    }
    payload.update(overrides)
    return payload


def club_host_payload(**overrides) -> dict:
    payload = draft_payload()
    payload["host"] = {"type": "club", "club_id": CLUB_ID}
    payload.update(overrides)
    return payload


def create_draft(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    response = client.post("/drafts", json=draft_payload(**overrides), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def fill_locales(client: TestClient, draft_id: str, headers: dict[str, str]) -> None:
    for code in ("en", "ru"):
        response = client.put(
            f"/drafts/{draft_id}/locales/{code}",
            json={"name": f"Event {code}", "description": f"Description {code}"},
            headers=headers,
        )
        assert response.status_code == 200, response.text


def submit(client: TestClient, draft_id: str, headers: dict[str, str]) -> dict:
    response = client.post(f"/submissions/{draft_id}", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def approve(client: TestClient, draft_id: str, moderator_headers: dict[str, str], feedback: str = "") -> dict:
    response = client.post(f"/submissions/{draft_id}/approve", json={"feedback": feedback}, headers=moderator_headers)
    assert response.status_code == 200, response.text
    return response.json()


def create_and_publish(
    client: TestClient,
    author_headers: dict[str, str],
    moderator_headers: dict[str, str],
    **overrides,
) -> dict:
    draft = create_draft(client, author_headers, **overrides)
    fill_locales(client, draft["id"], author_headers)
    submit(client, draft["id"], author_headers)
    approve(client, draft["id"], moderator_headers)
    return draft
