"""Test helpers for the Events service."""

import datetime as dtm
from urllib.parse import quote_plus

from fastapi.testclient import TestClient

from tests.events.conftest import CLUB_ID


def future_iso(days: int = 7) -> str:
    return (dtm.datetime.now(dtm.UTC) + dtm.timedelta(days=days)).isoformat()


def past_iso() -> str:
    return (dtm.datetime.now(dtm.UTC) - dtm.timedelta(days=1)).isoformat()


def maps_location_url(display_name: str) -> str:
    return f"https://innohassle.ru/maps?q={quote_plus(display_name)}"


def assert_resolved_location(location: dict | None, display_name: str, *, on_map: bool) -> None:
    assert location is not None
    assert location["display_name"] == display_name
    assert location["url"] == (maps_location_url(display_name) if on_map else "")


def draft_payload(**overrides) -> dict:
    payload: dict = {
        "starts_at": future_iso(),
        "location": "108",
        "locales": ["en", "ru"],
        "duration_hours": 2.0,
        "enrollment": {"type": "internal"},
    }
    payload.update(overrides)
    return payload


def create_draft(client: TestClient, headers: dict[str, str], **overrides) -> dict:
    response = client.post("/drafts", json=draft_payload(**overrides), headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def add_external_host(
    client: TestClient,
    draft_id: str,
    headers: dict[str, str],
    *,
    name: str = "One Zero Eight",
    url: str | None = None,
) -> dict:
    body: dict = {"name": name}
    if url is not None:
        body["url"] = url
    response = client.post(f"/drafts/{draft_id}/hosts/external", json=body, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def add_club_host(
    client: TestClient,
    draft_id: str,
    headers: dict[str, str],
    club_id: str = CLUB_ID,
) -> dict:
    response = client.post(f"/drafts/{draft_id}/hosts/clubs", json={"club_id": club_id}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def description_json(text: str) -> str:
    """Minimal TipTap doc JSON with a single paragraph of text."""
    import json

    return json.dumps(
        {
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [{"type": "text", "text": text}],
                }
            ],
        }
    )


def fill_locales(client: TestClient, draft_id: str, headers: dict[str, str]) -> None:
    for code in ("en", "ru"):
        response = client.put(
            f"/drafts/{draft_id}/locales/{code}",
            json={"name": f"Event {code}", "description": description_json(f"Description {code}")},
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
    *,
    host: str = "external",
    club_id: str = CLUB_ID,
    **overrides,
) -> dict:
    draft = create_draft(client, author_headers, **overrides)
    if host == "external":
        draft = add_external_host(client, draft["id"], author_headers)
    elif host == "club":
        draft = add_club_host(client, draft["id"], author_headers, club_id=club_id)
    fill_locales(client, draft["id"], author_headers)
    submit(client, draft["id"], author_headers)
    approve(client, draft["id"], moderator_headers)
    return draft
