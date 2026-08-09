import datetime as dtm
import re
from typing import cast

import icalendar
from fastapi.testclient import TestClient

from tests.events.conftest import CLUB_ID, CLUB_SLUG, CLUB_TITLE
from tests.events.helpers import create_and_publish, create_draft, future_iso, submit


def _parse_calendar(content: bytes) -> icalendar.Calendar:
    return icalendar.Calendar.from_ical(content)


def _vevents(calendar: icalendar.Calendar) -> list[icalendar.Event]:
    return [cast(icalendar.Event, component) for component in calendar.walk("VEVENT")]


def test_events_ics_includes_published_event_fields(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    draft = create_and_publish(events_client, user_headers, superadmin_headers, location="108")
    response = events_client.get("/events.ics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/calendar")

    calendar = _parse_calendar(response.content)
    assert b"BEGIN:VCALENDAR" in response.content
    events = _vevents(calendar)
    assert len(events) == 1
    vevent = events[0]
    assert str(vevent["summary"]) == "Event en"
    assert str(vevent["location"]) == "108"
    assert str(vevent["uid"]) == f"event-{draft['id']}@innohassle.ru"
    assert str(vevent["url"]).endswith(f"/events/p/{draft['id']}")
    assert str(vevent["description"]) == "Host: One Zero Eight"

    starts_at = vevent.decoded("dtstart")
    ends_at = vevent.decoded("dtend")
    assert isinstance(starts_at, dtm.datetime)
    assert isinstance(ends_at, dtm.datetime)
    assert ends_at - starts_at == dtm.timedelta(hours=2)


def test_events_ics_includes_resolved_club_host(
    events_client: TestClient,
    club_leader_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    create_and_publish(
        events_client, club_leader_headers, superadmin_headers, host={"type": "club", "club_id": CLUB_ID}
    )
    response = events_client.get("/events.ics")
    assert response.status_code == 200
    vevent = _vevents(_parse_calendar(response.content))[0]
    assert str(vevent["description"]) == f"Host: {CLUB_TITLE}\nhttps://innohassle.ru/clubs/{CLUB_SLUG}"


def test_events_ics_prefers_settings_locale_order(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    draft = create_draft(events_client, user_headers, locales=["en", "ru"])
    events_client.patch(
        f"/drafts/{draft['id']}/locales/en",
        json={"name": "English name", "description": "English description"},
        headers=user_headers,
    )
    events_client.patch(
        f"/drafts/{draft['id']}/locales/ru",
        json={"name": "Русское имя", "description": "Русское описание"},
        headers=user_headers,
    )
    submit(events_client, draft["id"], user_headers)
    events_client.post(f"/submissions/{draft['id']}/approve", json={"feedback": ""}, headers=superadmin_headers)

    response = events_client.get("/events.ics")
    assert response.status_code == 200
    vevent = _vevents(_parse_calendar(response.content))[0]
    assert str(vevent["summary"]) == "English name"


def test_events_ics_falls_back_to_available_locale(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    draft = create_draft(events_client, user_headers, locales=["ru"])
    events_client.patch(
        f"/drafts/{draft['id']}/locales/ru",
        json={"name": "Только русский", "description": "Описание"},
        headers=user_headers,
    )
    submit(events_client, draft["id"], user_headers)
    events_client.post(f"/submissions/{draft['id']}/approve", json={"feedback": ""}, headers=superadmin_headers)

    response = events_client.get("/events.ics")
    assert response.status_code == 200
    vevent = _vevents(_parse_calendar(response.content))[0]
    assert str(vevent["summary"]) == "Только русский"


def test_events_ics_excludes_unpublished_drafts(
    events_client: TestClient,
    user_headers: dict[str, str],
    superadmin_headers: dict[str, str],
):
    create_draft(events_client, user_headers)
    published = create_and_publish(events_client, user_headers, superadmin_headers, starts_at=future_iso(3))

    response = events_client.get("/events.ics")
    assert response.status_code == 200
    events = _vevents(_parse_calendar(response.content))
    assert len(events) == 1
    assert str(events[0]["uid"]) == f"event-{published['id']}@innohassle.ru"
    assert re.search(rf"URL:.*{re.escape(published['id'])}", response.text)
