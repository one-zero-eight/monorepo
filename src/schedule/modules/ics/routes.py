from collections import defaultdict
from typing import Annotated, cast
from urllib.parse import unquote

import icalendar
from fastapi import APIRouter, Header, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from icalendar import vDDDTypes
from pydantic import HttpUrl
from starlette.responses import FileResponse, Response, StreamingResponse

from src.logging_ import logger
from src.schedule.config import settings
from src.schedule.dependencies import CURRENT_USER_ID_DEPENDENCY
from src.schedule.exceptions import EventGroupNotFoundException, ForbiddenException, ObjectNotFound
from src.schedule.modules.event_groups.repository import event_group_repository
from src.schedule.modules.ics.utils import (
    generate_ics_from_url,
    get_all_workshops_ics,
    get_moodle_ics,
    get_personal_event_groups_ics,
    get_personal_music_room_ics,
    get_personal_room_bookings,
    get_personal_sport_ics,
    get_personal_workshops_ics,
)
from src.schedule.modules.parse.utils import locate_ics_by_path
from src.schedule.modules.users.linked import LinkedCalendarView
from src.schedule.modules.users.repository import user_repository

router = APIRouter(prefix="", tags=["ICS"], route_class=AutoDeriveResponsesAPIRoute)


@router.get(
    "/users/me/all.ics",
    responses={
        200: {
            "description": "ICS file with schedule based on favorites (non-hidden)",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
    tags=["Users"],
)
async def get_current_user_schedule(user_id: CURRENT_USER_ID_DEPENDENCY) -> StreamingResponse:
    """
    Get schedule in ICS format for the current user
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    ical_generator = await get_personal_event_groups_ics(user)

    return StreamingResponse(
        content=ical_generator,
        media_type="text/calendar",
    )


@router.get(
    "/users/{user_id}/all.ics",
    responses={
        200: {
            "description": "ICS file with schedule based on favorites (non-hidden)",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
        **ForbiddenException.responses,
    },
    tags=["Users"],
)
async def get_user_schedule(user_id: int, access_key: str) -> StreamingResponse:
    """
    Get schedule in ICS format for the user; requires access key for `/users/{user_id}/all.ics` resource
    """

    user = await user_repository.read(user_id)

    if user is None:
        raise ObjectNotFound()

    resource_path = f"/users/{user_id}/all.ics"
    if not await user_repository.check_user_schedule_key(user_id, access_key, resource_path):
        raise ForbiddenException()

    ical_generator = await get_personal_event_groups_ics(user)

    return StreamingResponse(
        content=ical_generator,
        media_type="text/calendar",
    )


@router.get(
    "/users/me/music-room.ics",
    responses={
        200: {
            "description": "ICS file with schedule of the music room booking",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
    },
    tags=["Users"],
)
async def get_music_room_current_user_schedule(user_id: CURRENT_USER_ID_DEPENDENCY) -> StreamingResponse:
    """
    Get schedule in ICS format for the current user
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    ical_generator = await get_personal_music_room_ics(user)

    return StreamingResponse(content=ical_generator, media_type="text/calendar")


@router.get(
    "/users/{user_id}/music-room.ics",
    responses={
        200: {
            "description": "ICS file with schedule of the music room booking",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
        **ForbiddenException.responses,
    },
    tags=["Users"],
)
async def get_music_room_user_schedule(user_id: int, access_key: str) -> StreamingResponse:
    """
    Get schedule in ICS format for the user; requires access key for `/users/{user_id}/music-room.ics` resource
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    resource_path = f"/users/{user_id}/music-room.ics"
    if not await user_repository.check_user_schedule_key(user_id, access_key, resource_path):
        raise ForbiddenException()

    ical_generator = await get_personal_music_room_ics(user)

    return StreamingResponse(content=ical_generator, media_type="text/calendar")


@router.get(
    "/users/me/sport.ics",
    responses={
        200: {
            "description": "ICS file with your sport check-ins",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
    tags=["Users"],
)
async def get_sport_current_user_schedule(user_id: CURRENT_USER_ID_DEPENDENCY) -> Response:
    """
    Get schedule in ICS format for the current user
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    ical_bytes = await get_personal_sport_ics(user)
    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/users/{user_id}/sport.ics",
    responses={
        200: {
            "description": "ICS file with your sport check-ins",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
        **ForbiddenException.responses,
    },
    tags=["Users"],
)
async def get_sport_user_schedule(user_id: int, access_key: str) -> Response:
    """
    Get schedule in ICS format for the user; requires access key for `/users/{user_id}/sport.ics` resource
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    resource_path = f"/users/{user_id}/sport.ics"
    if not await user_repository.check_user_schedule_key(user_id, access_key, resource_path):
        raise ForbiddenException()

    ical_bytes = await get_personal_sport_ics(user)
    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/users/me/workshops.ics",
    responses={
        200: {
            "description": "ICS file with your workshops check-ins",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
    tags=["Users"],
)
async def get_workshops_current_user_schedule(user_id: CURRENT_USER_ID_DEPENDENCY) -> Response:
    """
    Get schedule in ICS format for the current user
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    ical_bytes = await get_personal_workshops_ics(user)
    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/users/{user_id}/workshops.ics",
    responses={
        200: {
            "description": "ICS file with your workshops check-ins",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
    },
    tags=["Users"],
)
async def get_workshops_user_schedule(user_id: int, access_key: str) -> Response:
    """
    Get schedule in ICS format for the user; requires access key for `/users/{user_id}/workshops.ics` resource
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    resource_path = f"/users/{user_id}/workshops.ics"
    if not await user_repository.check_user_schedule_key(user_id, access_key, resource_path):
        raise ForbiddenException()

    ical_bytes = await get_personal_workshops_ics(user)
    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/users/me/moodle.ics",
    responses={
        200: {
            "description": "ICS file with your schedule from moodle",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
        **ForbiddenException.responses,
    },
    tags=["Users"],
)
async def get_moodle_user_schedule(user_id: CURRENT_USER_ID_DEPENDENCY) -> Response:
    """
    Get schedule in ICS format for the current user
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    if user.moodle_userid is None or user.moodle_calendar_authtoken is None:
        raise HTTPException(status_code=404, detail="Moodle for user is not configured")

    ical_bytes = await get_moodle_ics(user)

    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/users/{user_id}/moodle.ics",
    responses={
        200: {
            "description": "ICS file with your schedule from moodle",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
        **ForbiddenException.responses,
    },
    tags=["Users"],
)
async def get_moodle_current_user_schedule(user_id: int, access_key: str) -> Response:
    """
    Get schedule in ICS format for the user; requires access key for `/users/{user_id}/moodle.ics` resource
    """

    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    resource_path = f"/users/{user_id}/moodle.ics"
    if not await user_repository.check_user_schedule_key(user_id, access_key, resource_path):
        raise ForbiddenException()

    if user.moodle_userid is None or user.moodle_calendar_authtoken is None:
        raise HTTPException(status_code=404, detail="Moodle for user is not configured")

    ical_bytes = await get_moodle_ics(user)

    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/me/check-calendar-url-to-link",
    responses={
        200: {
            "description": "Calendar can be processed by the server",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        400: {"description": "Calendar can't be processed by the server"},
    },
)
async def check_calendar_url(user_id: CURRENT_USER_ID_DEPENDENCY, calendar_url: HttpUrl) -> Response:
    """
    Check if calendar url can be processed by the server
    """

    ical_generator = generate_ics_from_url(str(calendar_url))
    ical_bytes = b"".join([chunk async for chunk in ical_generator])

    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/users/{user_id}/linked/{linked_alias}.ics",
    responses={
        200: {
            "description": "ICS file with schedule based on linked url",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
    },
    tags=["Users"],
)
async def get_user_linked_schedule(user_id: int, linked_alias: str) -> Response:
    """
    Get schedule in ICS format for the user
    """

    user = await user_repository.read(user_id)

    if user is None:
        raise ObjectNotFound(f"User with id {user_id} not found")

    if linked_alias not in user.linked_calendars:
        raise ObjectNotFound(f"Linked calendar with alias {linked_alias} not found")

    linked_calendar: LinkedCalendarView = user.linked_calendars[linked_alias]

    ical_generator = generate_ics_from_url(linked_calendar.url)
    ical_bytes = b"".join([chunk async for chunk in ical_generator])

    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/music-room.ics",
    responses={
        200: {
            "description": "ICS file with schedule of the music room",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        404: {"description": "Music room is not configured"},
    },
    response_class=StreamingResponse,
)
async def get_music_room_schedule() -> StreamingResponse:
    """
    Get schedule in ICS format for the music room
    """
    if settings.music_room is None:
        raise HTTPException(status_code=404, detail="Music room is not configured")

    ical_generator = generate_ics_from_url(f"{settings.music_room.api_url}/music-room.ics", should_validate_url=False)

    return StreamingResponse(content=ical_generator, media_type="text/calendar")


@router.get(
    "/workshops.ics",
    responses={
        200: {
            "description": "ICS file with all workshops",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        404: {"description": "Workshops are not configured"},
    },
)
async def get_workshops_schedule(only_published: bool = True) -> Response:
    """
    Get schedule in ICS format for workshops.
    By default, returns only active non-draft workshops.
    """
    ical_bytes = await get_all_workshops_ics(only_published=only_published)
    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/{event_group_alias}.ics",
    response_class=FileResponse,
    responses={
        200: {
            "description": "ICS file with schedule of the event-group",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **EventGroupNotFoundException.responses,
        501: {"description": "Path is not set for this event group, on-the-fly .ics not supported"},
    },
    tags=["Event Groups"],
)
async def get_event_group_ics_by_alias(
    user_id: int,
    export_type: str,
    event_group_alias: str,
    user_agent: Annotated[str | None, Header()] = None,
):
    """
    Get event group .ics file by id
    """

    event_group_alias = unquote(event_group_alias)
    event_group = await event_group_repository.read_by_alias(event_group_alias)
    logger.info(f"User-Agent: {user_agent}")

    if event_group is None:
        raise EventGroupNotFoundException()
    if event_group.path:
        try:
            ics_path = locate_ics_by_path(event_group.path)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if user_agent == "Google-Calendar-Importer":  # patch reccurrences for Google Calendar
            with ics_path.open() as f:
                calendar: icalendar.Calendar = icalendar.Calendar.from_ical(f.read())
            events = []
            with_rrule: dict[str, icalendar.Event] = {}
            with_recurrence_id: dict[str, list[icalendar.Event]] = defaultdict(list)
            for event in calendar.walk("VEVENT"):
                event = cast(icalendar.Event, event)
                if event.get("RRULE"):
                    with_rrule[event.get("UID")] = event
                if recurrence_id := event.get("RECURRENCE-ID"):
                    with_recurrence_id[event.get("UID")].append(vDDDTypes.from_ical(recurrence_id))
                events.append(event)
            for uid, recurrence_ids in with_recurrence_id.items():
                parent: icalendar.Event = with_rrule[uid]
                if not parent.get("EXDATE"):
                    parent.add("EXDATE", recurrence_ids[0] if len(recurrence_ids) == 1 else recurrence_ids)
            calendar.subcomponents = list(filter(lambda component: component.name != "VEVENT", calendar.subcomponents))
            calendar.subcomponents.extend(events)
            return Response(content=calendar.to_ical(), media_type="text/calendar")
        else:
            return FileResponse(ics_path, media_type="text/calendar")
    else:
        # TODO: create ics file on the fly from events connected to event group
        raise HTTPException(
            status_code=501, detail="Can not create .ics file on the fly (set static .ics file for the event group)"
        )


@router.get(
    "/users/me/room-bookings.ics",
    responses={
        200: {
            "description": "ICS file with room bookings",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
    },
)
async def get_current_user_room_bookings(user_id: CURRENT_USER_ID_DEPENDENCY) -> Response:
    """
    Get bookings in ICS format for the room bookings
    """
    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    ical_bytes = await get_personal_room_bookings(user)
    return Response(content=ical_bytes, media_type="text/calendar")


@router.get(
    "/users/{user_id}/room-bookings.ics",
    responses={
        200: {
            "description": "ICS file with room bookings",
            "content": {"text/calendar": {"schema": {"type": "string", "format": "binary"}}},
        },
        **ObjectNotFound.responses,
        **ForbiddenException.responses,
    },
)
async def get_user_room_bookings(user_id: int, access_key: str) -> Response:
    """
    Get bookings in ICS format for the room bookings;
    Requires access key for `/users/{user_id}/room-bookings.ics` resource
    """
    user = await user_repository.read(user_id)
    if user is None:
        raise ObjectNotFound()

    resource_path = f"/users/{user_id}/room-bookings.ics"
    if not await user_repository.check_user_schedule_key(user_id, access_key, resource_path):
        raise ForbiddenException()

    ical_bytes = await get_personal_room_bookings(user)
    return Response(content=ical_bytes, media_type="text/calendar")
