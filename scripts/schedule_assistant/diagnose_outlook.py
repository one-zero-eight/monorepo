"""Read-only, bounded comparison of BMP and resource calendars.

Run from the repository root with ``python -m scripts.schedule_assistant.diagnose_outlook``.
No subscriptions, meeting changes, message read flags, or database writes are performed.
"""

import argparse
import datetime as dtm
import hashlib
import json
from collections import Counter
from typing import Any
from zoneinfo import ZoneInfo

import exchangelib
import exchangelib.errors
from exchangelib.protocol import BaseProtocol

MSK = ZoneInfo("Europe/Moscow")
READ_LIMIT = 250


def identity_token(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode()).hexdigest()[:20]


def calendar_records(account: exchangelib.Account, start: dtm.datetime, end: dtm.datetime) -> list[Any]:
    """Split full or capped CalendarViews until completeness is established.

    Exact-limit responses are treated as potentially truncated. A single unresolvable
    interval fails explicitly rather than claiming that a partially read room is free.
    """
    try:
        records = list(
            account.calendar.view(
                start=exchangelib.EWSDateTime.from_datetime(start),
                end=exchangelib.EWSDateTime.from_datetime(end),
                max_items=READ_LIMIT,
            ).only(
                "subject",
                "start",
                "end",
                "uid",
                "type",
                "required_attendees",
                "resources",
                "my_response_type",
                "legacy_free_busy_status",
                "is_cancelled",
            )
        )
    except exchangelib.errors.ErrorExceededFindCountLimit:
        records = None
    if records is not None and len(records) < READ_LIMIT:
        return records
    if end - start <= dtm.timedelta(minutes=1):
        raise RuntimeError("CalendarView cannot establish complete coverage of this interval")
    middle = start + (end - start) / 2
    combined = [*calendar_records(account, start, middle), *calendar_records(account, middle, end)]
    return list({(item.id, item.start): item for item in combined}.values())


def item_record(item: Any, *, response: str | None) -> dict[str, Any]:
    return {
        "subject": item.subject,
        "start": item.start.astimezone(MSK).isoformat(),
        "end": item.end.astimezone(MSK).isoformat(),
        "uid_token": identity_token(item.uid),
        "item_token": identity_token(item.id),
        "type": item.type,
        "response": response,
        "busy_type": item.legacy_free_busy_status,
        "cancelled": item.is_cancelled,
    }


def compare_items(organizer: list[Any], room: list[Any], room_email: str) -> list[dict[str, Any]]:
    result = []
    for item in organizer:
        attendees = [*(item.required_attendees or []), *(item.resources or [])]
        attendee = next(
            (a for a in attendees if (a.mailbox.email_address or "").casefold() == room_email.casefold()), None
        )
        if attendee is None:
            continue
        matches = [other for other in room if item.uid and other.uid == item.uid and other.start == item.start]
        record = item_record(item, response=attendee.response_type)
        record["room_presence"] = "present" if matches else "absent"
        record["room_copies"] = [item_record(other, response=other.my_response_type) for other in matches]
        result.append(record)
    return result


def build_report(start: dtm.date, end: dtm.date, room_ids: list[str], course: str | None) -> dict[str, Any]:
    from src.room_booking.config import settings
    from src.room_booking.modules.rooms.repository import room_repository

    BaseProtocol.TIMEOUT = 30
    exchange = settings.exchange
    config = exchangelib.Configuration(
        service_endpoint=exchange.ews_endpoint,
        credentials=exchangelib.Credentials(exchange.bmp.username, exchange.bmp.password.get_secret_value()),
        auth_type=exchangelib.BASIC,
        version=exchangelib.Version(exchangelib.version.EXCHANGE_2016),
        max_connections=1,
    )
    organizer = exchangelib.Account(
        exchange.bmp.username, autodiscover=False, access_type=exchangelib.DELEGATE, config=config
    )
    report: dict[str, Any] = {
        "checked_at": dtm.datetime.now(MSK).isoformat(),
        "read_only": True,
        "start": start.isoformat(),
        "end_inclusive": end.isoformat(),
        "complete": True,
        "days": [],
    }
    rooms = {}
    for room_id in room_ids:
        description = room_repository.get_by_id(room_id)
        if description is None:
            raise ValueError(f"Unknown room: {room_id}")
        rooms[room_id] = description
    date = start
    while date <= end:
        day_start = dtm.datetime.combine(date, dtm.time.min, tzinfo=MSK)
        day_end = day_start + dtm.timedelta(days=1)
        try:
            organizer_items = calendar_records(organizer, day_start, day_end)
        except Exception as error:  # noqa: BLE001 — report incomplete evidence without leaking server credentials
            report["complete"] = False
            report["days"].append({"date": date.isoformat(), "source": "organizer", "error": type(error).__name__})
            date += dtm.timedelta(days=1)
            continue
        for room_id, description in rooms.items():
            try:
                room_account = exchangelib.Account(
                    description.resource_email, autodiscover=False, access_type=exchangelib.DELEGATE, config=config
                )
                room_items = calendar_records(room_account, day_start, day_end)
                comparisons = compare_items(organizer_items, room_items, description.resource_email)
                if course:
                    comparisons = [row for row in comparisons if course.casefold() in (row["subject"] or "").casefold()]
                displayed_room = [
                    item_record(item, response=item.my_response_type)
                    for item in room_items
                    if not course or course.casefold() in (item.subject or "").casefold()
                ]
                report["days"].append(
                    {
                        "date": date.isoformat(),
                        "room": room_id,
                        "complete": True,
                        "organizer_events": comparisons,
                        "room_events": displayed_room,
                        "presence_counts": dict(Counter(row["room_presence"] for row in comparisons)),
                    }
                )
            except Exception as error:  # noqa: BLE001 — report incomplete evidence without leaking server credentials
                report["complete"] = False
                report["days"].append(
                    {
                        "date": date.isoformat(),
                        "room": room_id,
                        "complete": False,
                        "room_presence": "unknown",
                        "error": type(error).__name__,
                    }
                )
        date += dtm.timedelta(days=1)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=dtm.date.fromisoformat, required=True)
    parser.add_argument("--end", type=dtm.date.fromisoformat, required=True, help="Inclusive end, at most 62 days")
    parser.add_argument("--room", action="append", required=True)
    parser.add_argument("--course", help="Optional subject substring; identity matching still uses UID and start")
    args = parser.parse_args()
    if not 0 <= (args.end - args.start).days < 62:
        parser.error("Choose an inclusive interval of 1–62 days")
    try:
        report = build_report(args.start, args.end, args.room, args.course)
    except Exception as error:  # noqa: BLE001 — report incomplete evidence without leaking server credentials
        print(json.dumps({"complete": False, "error": type(error).__name__}))
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
