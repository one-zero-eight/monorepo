"""ICS feed builders for published events."""

import datetime as dtm

import icalendar

from src.events.config import settings
from src.events.mongo import Event, PublicEvent
from src.events.schemas import PublicHost
from src.events.service import pick_event_name


def _host_description(host: PublicHost) -> str:
    lines = [f"Host: {host.display_name}"]
    if host.link:
        lines.append(host.link)
    return "\n".join(lines)


def _event_to_vevent(event: Event, public: PublicEvent, host: PublicHost) -> icalendar.Event | None:
    summary = pick_event_name(public.data.locales)
    if summary is None:
        return None

    starts_at = public.data.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=dtm.UTC)
    ends_at = starts_at + dtm.timedelta(hours=settings.ics_default_duration_hours)

    vevent = icalendar.Event()
    vevent.add("uid", f"event-{event.id}@innohassle.ru")
    vevent.add("summary", summary)
    vevent.add("dtstart", icalendar.vDatetime(starts_at))
    vevent.add("dtend", icalendar.vDatetime(ends_at))
    vevent.add("url", f"{settings.innohassle_url.rstrip('/')}/events/p/{event.id}")
    vevent.add("description", _host_description(host))
    location = (public.data.location or "").strip()
    if location:
        vevent.add("location", location)
    return vevent


def build_events_ics(events: list[Event], hosts: dict[str, PublicHost]) -> bytes:
    calendar = icalendar.Calendar(
        prodid="-//one-zero-eight//InNoHassle Events",
        version="2.0",
        method="PUBLISH",
    )
    calendar["x-wr-calname"] = "Events from innohassle.ru"
    calendar["x-wr-caldesc"] = "Published events from InNoHassle"

    for event in events:
        if event.public is None:
            continue
        host = hosts.get(str(event.id))
        if host is None:
            continue
        vevent = _event_to_vevent(event, event.public, host)
        if vevent is not None:
            calendar.add_component(vevent)

    return calendar.to_ical()
