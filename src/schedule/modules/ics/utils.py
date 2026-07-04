import asyncio
import datetime as dtm
import html
import ipaddress
import socket
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, urlparse
from zlib import crc32

import aiofiles
import httpx
import icalendar
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger
from src.schedule.config import settings
from src.schedule.modules.event_groups.repository import event_group_repository
from src.schedule.modules.parse.utils import aware_utcnow, get_base_calendar, locate_ics_by_path
from src.schedule.modules.predefined.repository import predefined_repository
from src.schedule.modules.users.schemas import ViewUser

TIMEOUT = 60
MAX_SIZE = 10 * 1024 * 1024
MOSCOW_TZ = dtm.timezone(dtm.timedelta(hours=3), name="Europe/Moscow")
WORKSHOPS_ALL_LIMIT = 10_000


def _as_event(component: object) -> icalendar.Event:
    return cast(icalendar.Event, component)


def _prop_dt(prop: object) -> dtm.datetime:
    return cast(dtm.datetime, cast(Any, prop).dt)


def _prop_str(prop: object) -> str:
    return str(cast(Any, prop))


def _to_ical_str(prop: object) -> str:
    raw = cast(Any, prop).to_ical()
    return raw.decode(encoding="utf-8") if isinstance(raw, bytes) else str(raw)


def _validate_public_https_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme.lower() != "https":
        raise HTTPException(status_code=400, detail="Only https URLs are allowed")
    if parsed.hostname is None:
        raise HTTPException(status_code=400, detail="URL must contain a hostname")
    if parsed.port is not None:
        raise HTTPException(status_code=400, detail="Explicit port in URL is not allowed")
    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(status_code=400, detail="User info in URL is not allowed")

    hostname = parsed.hostname
    try:
        addrinfo = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise HTTPException(status_code=400, detail=f"Could not resolve hostname: {hostname}") from e

    if not addrinfo:
        raise HTTPException(status_code=400, detail=f"Could not resolve hostname: {hostname}")

    for entry in addrinfo:
        ip_raw = entry[4][0]
        ip = ipaddress.ip_address(ip_raw)
        if not ip.is_global:
            raise HTTPException(status_code=400, detail=f"URL resolves to non-public IP: {ip}")


async def generate_ics_from_url(
    url: str, headers: dict | None = None, should_validate_url=True
) -> AsyncGenerator[bytes]:
    if should_validate_url:
        _validate_public_https_url(url)
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, timeout=TIMEOUT, headers=headers, follow_redirects=False)
            logger.info(f"Response: {response.status_code}, {response.headers}")
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            # reraise as HTTPException
            raise HTTPException(
                status_code=400,
                detail=f"Error fetching calendar from {url}, {e.response.status_code}: {e.response.text}",
            ) from e

        _size = response.headers.get("Content-Length")
        if _size is not None:
            content_length = int(_size)
            if content_length > MAX_SIZE:
                raise HTTPException(status_code=400, detail=f"File is too big: {content_length}")

        ics_content = await response.aread()
        if len(ics_content) > MAX_SIZE:
            raise HTTPException(status_code=400, detail="File is too big")
        try:
            calendar = icalendar.Calendar.from_ical(ics_content)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid ICS format") from e

        yield calendar.to_ical()


async def _generate_ics_from_multiple(user: ViewUser, *ics: Path) -> AsyncGenerator[bytes]:
    async def _async_read_schedule(ics_path: Path):
        async with aiofiles.open(ics_path) as f:
            content = await f.read()
            _cal = icalendar.Calendar.from_ical(content)
            return _cal

    tasks = [_async_read_schedule(ics_path) for ics_path in ics]
    calendars = await asyncio.gather(*tasks)
    main_calendar = get_base_calendar()
    main_calendar["x-wr-calname"] = f"{user.email} schedule from innohassle.ru"
    ical_bytes = main_calendar.to_ical()
    # remove END:VCALENDAR
    ical_bytes = ical_bytes.removesuffix(b"END:VCALENDAR\r\n")
    yield ical_bytes

    for calendar in calendars:
        calendar: icalendar.Calendar
        vevents = calendar.walk(name="VEVENT")
        for vevent in vevents:
            vevent: icalendar.Event
            vevent["x-wr-origin"] = calendar["x-wr-calname"]
            yield vevent.to_ical()
    yield b"END:VCALENDAR"


async def get_personal_event_groups_ics(user: ViewUser) -> AsyncGenerator[bytes]:
    hidden = set(user.hidden_event_groups)
    predefined = await predefined_repository.get_user_predefined(user.id)
    all_user_event_groups = set(user.favorite_event_groups) | set(predefined)

    nonhidden = all_user_event_groups - hidden
    paths = set()
    for event_group_id in nonhidden:
        event_group = await event_group_repository.read(event_group_id)
        if event_group is None:
            continue
        if event_group.path is None:
            raise HTTPException(
                status_code=501,
                detail="Can not create .ics file for event group on the fly (set static .ics file for the event group",
            )
        try:
            ics_path = locate_ics_by_path(event_group.path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        paths.add(ics_path)
    ical_generator = _generate_ics_from_multiple(user, *paths)
    return ical_generator


async def get_personal_music_room_ics(user: ViewUser) -> AsyncGenerator[bytes]:
    if settings.music_room is None:
        raise HTTPException(status_code=404, detail="Music room is not configured")
    # check if user registered in music room
    async with httpx.AsyncClient() as client:
        url = f"{settings.music_room.api_url}/users/user_id"
        query_params = {"email": user.email}
        headers = {"Authorization": f"Bearer {settings.music_room.api_key.get_secret_value()}"}
        response = await client.get(url, params=query_params, headers=headers)
        response.raise_for_status()
        if response.status_code == 200:
            user_id = response.json()
            if user_id is None:
                raise HTTPException(status_code=404, detail="User not found in music room service")
        else:
            raise HTTPException(status_code=500, detail="Error in music room service")
    ical_generator = generate_ics_from_url(
        f"{settings.music_room.api_url}/users/{user_id}/bookings.ics",
        headers={"Authorization": f"Bearer {settings.music_room.api_key.get_secret_value()}"},
        should_validate_url=False,
    )
    return ical_generator


def _workshop_to_vevent(workshop: dict) -> icalendar.Event:
    string_to_hash = str(workshop["id"])
    hash_ = crc32(string_to_hash.encode("utf-8"))
    uid = f"workshop-{abs(hash_):x}@innohassle.ru"

    vevent = icalendar.Event()
    vevent.add("uid", uid)

    vevent.add("summary", workshop["english_name"])
    if workshop.get("place") is not None:
        vevent.add("location", workshop["place"])
    if workshop.get("english_description") is not None:
        vevent.add("description", workshop["english_description"])
    _dtstart = dtm.datetime.fromisoformat(workshop["dtstart"])
    _dtstart = _dtstart.astimezone(MOSCOW_TZ)
    _dtend = dtm.datetime.fromisoformat(workshop["dtend"])
    _dtend = _dtend.astimezone(MOSCOW_TZ)
    vevent.add("dtstart", icalendar.vDatetime(_dtstart))
    vevent.add("dtend", icalendar.vDatetime(_dtend))
    vevent.add("x-workshop-id", workshop["id"])
    return vevent


async def _fetch_workshops(path: str, params: dict | None = None) -> list[dict]:
    if settings.workshops is None:
        raise HTTPException(status_code=404, detail="Workshops are not configured")

    async with httpx.AsyncClient(
        headers={"Authorization": f"Bearer {settings.workshops.api_key.get_secret_value()}"}, timeout=TIMEOUT
    ) as client:
        response = await client.get(f"{settings.workshops.api_url}{path}", params=params)
        if response.status_code == 404 and "User not found" in response.text:
            raise HTTPException(status_code=404, detail="User not found in workshops service")
        response.raise_for_status()
        return response.json()


def _generate_workshops_ics(workshops: list[dict], calendar_name: str) -> bytes:
    main_calendar = get_base_calendar()
    main_calendar["x-wr-calname"] = calendar_name

    for workshop in workshops:
        event = _workshop_to_vevent(workshop)
        main_calendar.add_component(event)

    return main_calendar.to_ical()


async def get_all_workshops_ics(only_published: bool = True) -> bytes:
    workshops = await _fetch_workshops("/workshops/", params={"limit": WORKSHOPS_ALL_LIMIT})
    if only_published:
        workshops = [
            workshop
            for workshop in workshops
            if workshop.get("is_draft") is False
            and workshop.get("is_active") is True
            and workshop.get("is_approved") is True
        ]
    return _generate_workshops_ics(workshops, "Workshops schedule from innohassle.ru")


async def get_personal_workshops_ics(user: ViewUser) -> bytes:
    """
    GET */users/{innohassle_user_id}/checkins

    [
        {
            "id": "b1d378a5-fe1b-47c6-b920-12acf77fcf1a",
            "dtstart": "2025-08-15T18:40:30.289000Z",
            "dtend": "2025-08-15T18:59:30.289000Z",
            "name": "W3",
            "description": null,
            "place": null,
        },
        ...
    ]
    """

    workshops = await _fetch_workshops(f"/users/{user.innohassle_id}/checkins")
    return _generate_workshops_ics(workshops, f"{user.email} Events schedule from innohassle.ru")


class Training(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    class ExtendedProps(BaseModel):
        id: int
        group_id: int
        can_grade: bool
        training_class: str | None
        group_accredited: bool
        can_check_in: bool
        checked_in: bool

    title: str
    start: dtm.datetime
    end: dtm.datetime
    all_day: bool = Field(default=False, alias="allDay")
    extended_props: ExtendedProps = Field(alias="extendedProps")


async def get_personal_sport_ics(user: ViewUser) -> bytes:
    """
    GET /calendar/trainings

    [
      {
        "title": "Football",
        "start": "2024-03-09T17:00:00+03:00",
        "end": "2024-03-09T19:00:00+03:00",
        "allDay": false,
        "extendedProps": {
          "id": 32133,
          "can_edit": true,
          "group_id": 560,
          "can_grade": false,
          "training_class": "[SC] Big Hall",
          "group_accredited": true,
          "can_check_in": false,
          "checked_in": false
        }
      },
      {
        "title": "Table tennis - Beginners",
        "start": "2024-03-10T10:00:00+03:00",
        "end": "2024-03-10T11:30:00+03:00",
        "allDay": false,
        "extendedProps": {
          "id": 31640,
          "can_edit": true,
          "group_id": 551,
          "can_grade": false,
          "training_class": "[SC] 2nd floor",
          "group_accredited": true,
          "can_check_in": false,
          "checked_in": false
        }
      }
    ]
    """

    def _training_to_vevent(training: Training) -> icalendar.Event:
        string_to_hash = str(training.extended_props.id)
        hash_ = crc32(string_to_hash.encode("utf-8"))
        uid = f"sport-{abs(hash_):x}@innohassle.ru"

        vevent = icalendar.Event()
        vevent.add("uid", uid)

        vevent.add("summary", training.title)
        if training.all_day:
            vevent.add("dtstart", icalendar.vDate(training.start.date()))
            vevent.add("dtend", icalendar.vDate(training.end.date()))
        else:
            vevent.add("dtstart", icalendar.vDatetime(training.start))
            vevent.add("dtend", icalendar.vDatetime(training.end))
        if training.extended_props.training_class is not None:
            vevent.add("location", training.extended_props.training_class)
        vevent.add("x-sport-training-id", training.extended_props.id)
        vevent.add("x-sport-checked-in", training.extended_props.checked_in)
        vevent.add("x-sport-can-checkin", training.extended_props.can_check_in)
        return vevent

    if user.innohassle_id is None:
        raise HTTPException(status_code=404, detail="User has no innohassle account linked")

    main_calendar = get_base_calendar()
    main_calendar["x-wr-calname"] = f"{user.email} Sport schedule from innohassle.ru"

    sport_token = await inh_accounts.get_sport_token(user.innohassle_id)
    _now = aware_utcnow()
    _start = _now - dtm.timedelta(days=7)
    _end = _now + dtm.timedelta(days=7)

    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {sport_token}"}, timeout=TIMEOUT) as client:
        response = await client.get(
            f"{settings.sport.api_url}/calendar/trainings",
            params={"start": _start.isoformat(), "end": _end.isoformat()},
        )
        response.raise_for_status()
        type_adapter = TypeAdapter(list[Training])
        trainings = type_adapter.validate_python(response.json())

    for training in trainings:
        if not training.extended_props.checked_in:
            continue
        event = _training_to_vevent(training)
        main_calendar.add_component(event)

    ical_bytes = main_calendar.to_ical()
    return ical_bytes


async def get_moodle_ics(user: ViewUser) -> bytes:
    """
    Get schedule in ICS format for the user from user link to moodle calendar;
    """

    def get_course_name(event: icalendar.Event) -> str:
        categories = _to_ical_str(event["categories"])
        course_name = html.unescape(categories.split("]")[1].replace(r"\;", ";"))
        return course_name

    def make_deadline(event: icalendar.Event) -> icalendar.Event:
        new = icalendar.Event()
        end = _prop_dt(event["dtend"])
        end = end.astimezone(MOSCOW_TZ)
        new["dtstart"] = icalendar.vDate(end.date())
        new["uid"] = event["uid"]
        new["dtstamp"] = event["dtstamp"]
        course_name = get_course_name(event)
        new["summary"] = _prop_str(event["summary"]) + f" - {course_name}"

        new["description"] = f"Course: {course_name}\nDue to: {end.timetz().isoformat()}"

        return new

    def create_quiz(quiz_name: str, opens: icalendar.Event, closes: icalendar.Event | None = None) -> icalendar.Event:
        new = icalendar.Event()
        start = _prop_dt(opens["dtstart"])
        start = start.astimezone(MOSCOW_TZ)
        due: dtm.datetime | None = None
        if closes:
            due = _prop_dt(closes["dtend"])
            due = due.astimezone(MOSCOW_TZ)
        if due and start.date() != due.date():  # Display only on deadline day
            new["dtstart"] = icalendar.vDate(due.date())
        else:
            new["dtstart"] = icalendar.vDatetime(start)
            if due:
                new["dtend"] = icalendar.vDatetime(due)

        new["uid"] = opens["uid"]
        new["dtstamp"] = opens["dtstamp"]
        course_name = get_course_name(opens)
        new["summary"] = quiz_name + f" - {course_name}"

        new["description"] = "\n".join(
            [
                f"Course: {course_name}",
                _prop_str(opens["description"]) if opens.get("description") else "",
                f"Due to: {due.timetz().isoformat()}" if due else "",
            ]
        ).strip()

        new["color"] = "darkorange"
        return new

    async def read_moodle_schedule(url: str) -> icalendar.Calendar:
        _generator = generate_ics_from_url(url)
        content = "".join([bytes_data.decode("utf-8") async for bytes_data in _generator if bytes_data is not None])
        calendar = icalendar.Calendar.from_ical(content)
        return calendar

    async def _async_fix_moodle_events(calendar: icalendar.Calendar) -> icalendar.Calendar:
        fixed_calendar = get_base_calendar()
        fixed_calendar["x-wr-calname"] = "Moodle"

        vevents = calendar.walk(name="VEVENT")
        fixed_events = []
        quizes_halfs_opens = {}
        quizes_halfs_closes = {}

        for raw_event in vevents:
            event = _as_event(raw_event)
            event_timedelta = _prop_dt(event["dtend"]) - _prop_dt(event["dtstart"])
            event_name = _prop_str(event["summary"]).strip()

            if event_timedelta == dtm.timedelta():
                if event_name.endswith("opens"):
                    quiz_name = event_name.split("opens", maxsplit=1)[0].strip()
                    if quiz_name in quizes_halfs_opens:
                        logger.warning(f"Quiz '{quiz_name}' appears twice")
                    quizes_halfs_opens[quiz_name] = event
                elif event_name.endswith("открывается"):
                    quiz_name = event_name.split("открывается", maxsplit=1)[0].strip()
                    if quiz_name in quizes_halfs_opens:
                        logger.warning(f"Quiz '{quiz_name}' appears twice")
                    quizes_halfs_opens[quiz_name] = event
                elif event_name.endswith("closes"):
                    quiz_name = event_name.split("closes", maxsplit=1)[0].strip()
                    if quiz_name in quizes_halfs_closes:
                        logger.warning(f"Quiz '{quiz_name}' appears twice")
                    quizes_halfs_closes[quiz_name] = event
                elif event_name.endswith("закрывается"):
                    quiz_name = event_name.split("закрывается", maxsplit=1)[0].strip()
                    if quiz_name in quizes_halfs_closes:
                        logger.warning(f"Quiz '{quiz_name}' appears twice")
                    quizes_halfs_closes[quiz_name] = event
                else:
                    # DEADLINE TYPE
                    deadline = make_deadline(event)
                    fixed_events.append(deadline)
            else:
                if "Attendance" in event_name:
                    continue

                categories = _to_ical_str(event["categories"])
                if categories:
                    if "]" in categories:
                        course_name = categories.split("]")[1]
                    else:
                        course_name = categories
                    event["summary"] = _prop_str(event["summary"]) + f" - {course_name}"
                    description = _prop_str(event["description"]) if event.get("description") else ""
                    event["description"] = "\n".join(
                        [
                            f"Course: {course_name}",
                            description,
                        ]
                    )

                start_prop = event["dtstart"]
                if start_prop:
                    start_dt = _prop_dt(start_prop).astimezone(MOSCOW_TZ)
                    event["dtstart"] = icalendar.vDatetime(start_dt)

                end_prop = event["dtend"]
                if end_prop:
                    end_dt = _prop_dt(end_prop).astimezone(MOSCOW_TZ)
                    event["dtend"] = icalendar.vDatetime(end_dt)

                fixed_events.append(event)

        for quiz_name, opens in quizes_halfs_opens.items():
            closes = quizes_halfs_closes.get(quiz_name)

            if closes:  # Paired
                quiz = create_quiz(quiz_name, opens, closes)
                fixed_events.append(quiz)
            else:  # Non pair (no deadline)
                quiz = create_quiz(quiz_name, opens, closes=None)
                fixed_events.append(quiz)

        for event in fixed_events:
            event["color"] = "darkorange"
            fixed_calendar.add_component(event)

        return fixed_calendar

    token = user.moodle_calendar_authtoken
    if token is None:
        raise HTTPException(status_code=404, detail="Moodle calendar token is not configured")
    encoded_token = quote(token)
    user_moodle_calendar_url = (
        f"https://moodle.innopolis.university/calendar/export_execute.php?"
        f"userid={user.moodle_userid}&authtoken={encoded_token}&preset_what=all&preset_time=custom"
    )
    moodle_calendar = await read_moodle_schedule(user_moodle_calendar_url)
    calendar = await _async_fix_moodle_events(moodle_calendar)
    return calendar.to_ical()


async def get_personal_room_bookings(user: ViewUser) -> bytes:
    """
    GET */user/{user_id}/bookings

    [
        {
            "id": 0,
            "room_id": "string",
            "title": "string",
            "start": "2026-02-04T20:07:51.866Z",
            "end": "2026-02-04T20:07:51.866Z"
        }
    ]
    """

    def _booking_to_vevent(booking: dict) -> icalendar.Event:
        string_to_hash = str(booking["outlook_booking_id"])
        hash_ = crc32(string_to_hash.encode("utf-8"))
        uid = f"room-booking-{abs(hash_):x}@innohassle.ru"

        vevent = icalendar.Event()
        vevent.add("uid", uid)

        vevent.add("summary", booking["title"])
        if booking.get("room_id"):
            vevent.add("location", booking["room_id"])

        _dtstart = dtm.datetime.fromisoformat(booking["start"])
        if _dtstart.tzinfo is None:
            _dtstart = _dtstart.replace(tzinfo=dtm.UTC)
        _dtstart = _dtstart.astimezone(MOSCOW_TZ)

        _dtend = dtm.datetime.fromisoformat(booking["end"])
        if _dtend.tzinfo is None:
            _dtend = _dtend.replace(tzinfo=dtm.UTC)
        _dtend = _dtend.astimezone(MOSCOW_TZ)

        vevent.add("dtstart", icalendar.vDatetime(_dtstart))
        vevent.add("dtend", icalendar.vDatetime(_dtend))
        vevent.add("x-room-booking-id", booking["outlook_booking_id"])
        return vevent

    if settings.room_booking is None:
        raise HTTPException(status_code=404, detail="Room booking service is not configured")

    main_calendar = get_base_calendar()
    main_calendar["x-wr-calname"] = f"{user.email} Room bookings from innohassle.ru"

    now_utc = dtm.datetime.now(dtm.UTC)
    start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)

    async with httpx.AsyncClient(
        base_url=settings.room_booking.api_url,
        headers={"Authorization": f"Bearer {settings.room_booking.api_key.get_secret_value()}"},
        timeout=TIMEOUT,
    ) as client:
        response = await client.get(
            f"/user/{user.innohassle_id}/bookings",
            params={
                "start": start_of_day.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": (now_utc + dtm.timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        response.raise_for_status()
        bookings = response.json()

    for booking in bookings:
        event = _booking_to_vevent(booking)
        main_calendar.add_component(event)

    ical_bytes = main_calendar.to_ical()
    return ical_bytes
