from urllib.parse import quote

import icalendar
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from tests.events.helpers import create_and_publish, create_draft, future_iso

EMAIL = "plain-user@innopolis.university"
PATH = f"/users/integrations/schedule/{quote(EMAIL, safe='')}/events.ics"
HEADERS = {"Authorization": "Bearer test-events-api-key"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong-key"}])
def test_schedule_feed_requires_service_key(events_client: TestClient, headers: dict[str, str]):
    response = events_client.get(PATH, headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["detail"] == "Invalid service API key"


def test_schedule_feed_rejects_user_jwt(events_client: TestClient, plain_user_headers: dict[str, str]):
    response = events_client.get(PATH, headers=plain_user_headers)
    assert response.status_code == 401


@pytest.mark.parametrize("key", [None, SecretStr("")])
def test_schedule_feed_disabled_without_key(
    events_client: TestClient, monkeypatch: pytest.MonkeyPatch, key: SecretStr | None
):
    from src.events.config import settings

    monkeypatch.setattr(settings, "api_key", key)
    response = events_client.get(PATH, headers=HEADERS)
    assert response.status_code == 503
    assert response.json()["detail"] == "Schedule integration is not configured"


def test_schedule_feed_matches_enrolled_user_feed(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
    plain_user_headers: dict[str, str],
):
    enrolled = create_and_publish(events_client, user_headers, superadmin_headers, starts_at=future_iso(2))
    create_and_publish(events_client, user_headers, superadmin_headers, starts_at=future_iso(3))
    unpublished = create_and_publish(events_client, user_headers, superadmin_headers, starts_at=future_iso(4))
    create_draft(events_client, user_headers)
    for event in (enrolled, unpublished):
        response = events_client.post(f"/events/{event['id']}/enroll", headers=plain_user_headers)
        assert response.status_code == 200
    assert events_client.delete(f"/events/{unpublished['id']}", headers=superadmin_headers).status_code == 200

    response = events_client.get(PATH, headers=HEADERS)
    personal = events_client.get("/users/me/events.ics", headers=plain_user_headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")
    assert response.content == personal.content
    events = icalendar.Calendar.from_ical(response.content).walk("VEVENT")
    assert len(events) == 1
    assert str(events[0]["uid"]) == f"event-{enrolled['id']}@innohassle.ru"
    assert EMAIL.encode() not in events[0].to_ical()


def test_schedule_feed_unknown_email_is_empty(events_client: TestClient):
    response = events_client.get("/users/integrations/schedule/unknown%40example.test/events.ics", headers=HEADERS)
    assert response.status_code == 200
    assert icalendar.Calendar.from_ical(response.content).walk("VEVENT") == []
