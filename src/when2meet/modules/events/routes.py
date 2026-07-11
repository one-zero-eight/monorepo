import asyncio
import datetime as dtm
from typing import cast
from urllib.parse import quote

import httpx
from beanie.odm.queries.update import UpdateResponse
from fastapi import APIRouter, HTTPException, Request, status
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import ValidationError

from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import UserSchema, inh_accounts
from src.logging_ import logger
from src.when2meet.config import settings
from src.when2meet.mongo import Event, Participant

from . import events_repo
from .schemas import (
    AvailableRoom,
    BookedRoom,
    BookRoomRequest,
    EventCreate,
    EventSummary,
    EventUpdate,
    EventView,
    ParticipantUpdate,
    ParticipantView,
    RoomBookingBooking,
    RoomBookingCanBook,
    RoomBookingCreatedBooking,
    RoomBookingRoom,
)

router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"],
    route_class=AutoDeriveResponsesAPIRoute,
)

type RoomBookingQueryParams = dict[str, str] | list[tuple[str, str | int | float | None]]
type RoomBookingJsonBody = dict[str, str | list[str] | None]
type RoomBookingPatchBody = dict[str, str | None]


def _build_participant_view(participant: Participant, user: UserSchema | None) -> ParticipantView:
    telegram_info = user.telegram_info if user else None
    telegram_username = telegram_info.username if telegram_info else None

    return ParticipantView(
        user_id=participant.user_id,
        email=user.innopolis_info.email if user and user.innopolis_info else None,
        name=user.innopolis_info.name if user and user.innopolis_info else None,
        telegram=f"@{telegram_username.lstrip('@')}" if telegram_username else None,
        availability=participant.availability,
    )


async def _event_view(event: Event) -> EventView:
    user_ids = list(dict.fromkeys(p.user_id for p in event.participants))
    users: dict[str, UserSchema | None] = {}

    if user_ids:
        try:
            users = await inh_accounts.get_users(user_ids)
        except (
            httpx.HTTPError,
            ValidationError,
            ValueError,
        ):
            logger.warning("Failed to enrich When2Meet participants from Accounts", exc_info=True)

    return EventView(
        **event.model_dump(exclude={"participants", "room_booking_in_progress"}),
        participants=[_build_participant_view(p, users.get(p.user_id)) for p in event.participants],
    )


def _event_summary(event: Event) -> EventSummary:
    return EventSummary(
        **event.model_dump(include={"id", "slug", "name", "description", "created_at", "selected_time"}),
        participants_count=len(event.participants),
    )


def _booking_overlaps(booking: RoomBookingBooking, start: dtm.datetime, end: dtm.datetime) -> bool:
    return booking.start < end and booking.end > start


def _room_view(room: RoomBookingRoom) -> AvailableRoom:
    return AvailableRoom(
        id=room.id,
        name=room.title,
        capacity=room.capacity,
        location=room.short_name,
    )


def _room_booking_url(path: str) -> str:
    room_booking_settings = settings.room_booking
    if room_booking_settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Room Booking integration is not configured",
        )

    return f"{room_booking_settings.api_url.rstrip('/')}/{path.lstrip('/')}"


def _room_booking_json(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError as exc:
        logger.warning("Room Booking API returned invalid JSON", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Room Booking API returned an invalid response",
        ) from exc


def _room_booking_error_detail(response: httpx.Response) -> object:
    try:
        data = response.json()
    except ValueError:
        return "Room Booking API returned an error"
    if isinstance(data, dict) and "detail" in data:
        return data["detail"]
    return data


async def _room_booking_get(path: str, params: RoomBookingQueryParams, user_auth_header: str) -> object:
    url = _room_booking_url(path)
    try:
        async with httpx.AsyncClient(headers={"Authorization": user_auth_header}, timeout=30) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Room Booking API returned an error", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Room Booking API returned an error",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Failed to call Room Booking API", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to call Room Booking API",
        ) from exc

    return _room_booking_json(response)


async def _room_booking_post(path: str, json_body: RoomBookingJsonBody, user_auth_header: str) -> object:
    url = _room_booking_url(path)
    try:
        async with httpx.AsyncClient(headers={"Authorization": user_auth_header}, timeout=30) as client:
            response = await client.post(url, json=json_body)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=_room_booking_error_detail(exc.response),
            ) from exc

        logger.warning("Room Booking API returned an error", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Room Booking API returned an error",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Failed to call Room Booking API", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to call Room Booking API",
        ) from exc

    return _room_booking_json(response)


async def _room_booking_patch(path: str, json_body: RoomBookingPatchBody, user_auth_header: str) -> object:
    url = _room_booking_url(path)
    try:
        async with httpx.AsyncClient(headers={"Authorization": user_auth_header}, timeout=30) as client:
            response = await client.patch(url, json=json_body)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=_room_booking_error_detail(exc.response),
            ) from exc

        logger.warning("Room Booking API returned an error", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Room Booking API returned an error",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Failed to call Room Booking API", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to call Room Booking API",
        ) from exc

    return _room_booking_json(response)


async def _room_booking_delete(path: str, user_auth_header: str) -> None:
    url = _room_booking_url(path)
    try:
        async with httpx.AsyncClient(headers={"Authorization": user_auth_header}, timeout=30) as client:
            response = await client.delete(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        }:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=_room_booking_error_detail(exc.response),
            ) from exc

        logger.warning("Room Booking API returned an error", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Room Booking API returned an error",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Failed to call Room Booking API", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to call Room Booking API",
        ) from exc


async def _get_rooms(user_auth_header: str) -> list[RoomBookingRoom]:
    rooms = cast(
        list[object],
        await _room_booking_get("/rooms/", params={"include_red": "true"}, user_auth_header=user_auth_header),
    )
    return [RoomBookingRoom.model_validate(room) for room in rooms]


async def _get_room_bookings(
    room_ids: list[str], start: dtm.datetime, end: dtm.datetime, user_auth_header: str
) -> list[RoomBookingBooking]:
    params: RoomBookingQueryParams = [
        ("start", start.isoformat()),
        ("end", end.isoformat()),
        *[("room_ids", room_id) for room_id in room_ids],
    ]
    bookings = cast(
        list[object], await _room_booking_get("/bookings/", params=params, user_auth_header=user_auth_header)
    )
    return [RoomBookingBooking.model_validate(booking) for booking in bookings]


async def _get_room_can_book(
    room_id: str, start: dtm.datetime, end: dtm.datetime, user_auth_header: str
) -> RoomBookingCanBook:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    can_book = await _room_booking_get(f"/room/{room_id}/can-book", params=params, user_auth_header=user_auth_header)
    return RoomBookingCanBook.model_validate(can_book)


async def _can_book_room(room_id: str, start: dtm.datetime, end: dtm.datetime, user_auth_header: str) -> bool:
    return (await _get_room_can_book(room_id, start, end, user_auth_header)).can_book


async def _get_available_rooms_for_time(
    start: dtm.datetime,
    end: dtm.datetime,
    user_auth_header: str,
) -> list[AvailableRoom]:
    rooms = await _get_rooms(user_auth_header)
    bookings = await _get_room_bookings(
        room_ids=[room.id for room in rooms],
        start=start,
        end=end,
        user_auth_header=user_auth_header,
    )
    busy_room_ids = {booking.room_id for booking in bookings if _booking_overlaps(booking, start, end)}
    free_rooms = [room for room in rooms if room.id not in busy_room_ids]

    can_book_flags = await asyncio.gather(
        *[_can_book_room(room.id, start, end, user_auth_header) for room in free_rooms]
    )
    return [_room_view(room) for room, can_book in zip(free_rooms, can_book_flags) if can_book]


async def _book_room(event: Event, room_id: str, user_auth_header: str) -> BookedRoom:
    if event.selected_time is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected meeting time is not set")

    can_book = await _get_room_can_book(room_id, event.selected_time.start, event.selected_time.end, user_auth_header)
    if not can_book.can_book:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=can_book.reason_why_cannot or "Room is unavailable for the selected meeting time",
        )

    booking = RoomBookingCreatedBooking.model_validate(
        await _room_booking_post(
            "/bookings/",
            json_body={
                "room_id": room_id,
                "title": event.name,
                "start": event.selected_time.start.isoformat(),
                "end": event.selected_time.end.isoformat(),
                "participant_emails": None,
                "recurrence": None,
                "categories": ["When2Meet"],
                "description": "Booked for When2Meet meeting",
            },
            user_auth_header=user_auth_header,
        )
    )
    return BookedRoom(
        room_id=booking.room_id,
        outlook_booking_id=booking.outlook_booking_id,
        outlook_entry_id=booking.outlook_entry_id,
    )


def _manageable_booking_id(booked_room: BookedRoom) -> str:
    if booked_room.outlook_booking_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stored room booking cannot be managed",
        )
    return booked_room.outlook_booking_id


def _manageable_booking_path(booked_room: BookedRoom) -> str:
    return f"/bookings/{quote(_manageable_booking_id(booked_room), safe='')}"


async def _cancel_room_booking(booked_room: BookedRoom, user_auth_header: str) -> None:
    await _room_booking_delete(_manageable_booking_path(booked_room), user_auth_header=user_auth_header)


async def _update_room_booking(event: Event, selected_time: bool, title: bool, user_auth_header: str) -> BookedRoom:
    if event.booked_room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room is not booked for this meeting")
    if event.selected_time is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected meeting time is not set")

    booking = RoomBookingCreatedBooking.model_validate(
        await _room_booking_patch(
            _manageable_booking_path(event.booked_room),
            json_body={
                "title": event.name,
                "start": event.selected_time.start.isoformat(),
                "end": event.selected_time.end.isoformat(),
            },
            user_auth_header=user_auth_header,
        )
    )
    return BookedRoom(
        room_id=booking.room_id,
        outlook_booking_id=booking.outlook_booking_id,
        outlook_entry_id=booking.outlook_entry_id,
    )


async def _acquire_room_booking_lock(event: Event, require_unbooked: bool = True) -> bool:
    filters: list[object] = [
        Event.id == event.id,
        {"$or": [{"room_booking_in_progress": False}, {"room_booking_in_progress": {"$exists": False}}]},
    ]
    if require_unbooked:
        filters.append({"booked_room": None})

    result = await Event.find_one(*filters).update(
        {"$set": {"room_booking_in_progress": True}},
        response_type=UpdateResponse.UPDATE_RESULT,
    )
    return result is not None and result.modified_count == 1


async def _release_room_booking_lock(event: Event) -> None:
    await Event.find_one(Event.id == event.id).update({"$set": {"room_booking_in_progress": False}})


async def _save_booked_room(event: Event, booked_room: BookedRoom) -> Event:
    updated_event = await Event.find_one(
        Event.id == event.id,
        {"booked_room": None},
        {"room_booking_in_progress": True},
    ).update(
        {
            "$set": {
                "booked_room": booked_room.model_dump(),
                "room_booking_in_progress": False,
            }
        },
        response_type=UpdateResponse.NEW_DOCUMENT,
    )
    if updated_event is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room is already booked for this meeting",
        )
    return updated_event


async def _replace_booked_room(event: Event, booked_room: BookedRoom | None) -> Event:
    updated_event = await Event.find_one(
        Event.id == event.id,
        {"room_booking_in_progress": True},
    ).update(
        {
            "$set": {
                "booked_room": booked_room.model_dump() if booked_room is not None else None,
                "room_booking_in_progress": False,
            }
        },
        response_type=UpdateResponse.NEW_DOCUMENT,
    )
    if updated_event is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room booking is already being changed for this meeting",
        )
    return updated_event


async def _require_room_booking_lock(event: Event, require_unbooked: bool, detail: str) -> None:
    if await _acquire_room_booking_lock(event, require_unbooked=require_unbooked):
        return
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


async def _locked_event_with_booked_room(event: Event) -> Event:
    locked_event = await Event.get(event.id)
    if locked_event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if locked_event.booked_room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room is not booked for this meeting")
    return locked_event


async def _update_meeting_room_booking(
    event: Event,
    event_update: EventUpdate,
    *,
    updates_booking_time: bool,
    updates_booking_title: bool,
    user_auth_header: str,
) -> Event:
    await _require_room_booking_lock(
        event,
        require_unbooked=False,
        detail="Room booking is already being changed for this meeting",
    )

    try:
        for field_name in event_update.model_fields_set:
            setattr(event, field_name, getattr(event_update, field_name))
        event.booked_room = await _update_room_booking(
            event,
            selected_time=updates_booking_time,
            title=updates_booking_title,
            user_auth_header=user_auth_header,
        )
        event.room_booking_in_progress = False
        return await event.save()
    except Exception:
        await _release_room_booking_lock(event)
        raise


async def _book_meeting_room(event: Event, room_id: str, user_auth_header: str) -> Event:
    await _require_room_booking_lock(
        event,
        require_unbooked=True,
        detail="Room booking is already in progress for this meeting",
    )

    try:
        booked_room = await _book_room(event, room_id, user_auth_header)
    except Exception:
        await _release_room_booking_lock(event)
        raise

    return await _save_booked_room(event, booked_room)


async def _change_meeting_room(event: Event, room_id: str, user_auth_header: str) -> Event:
    await _require_room_booking_lock(
        event,
        require_unbooked=False,
        detail="Room booking is already being changed for this meeting",
    )

    new_booked_room: BookedRoom | None = None
    try:
        locked_event = await _locked_event_with_booked_room(event)
        old_booked_room = cast(BookedRoom, locked_event.booked_room)
        new_booked_room = await _book_room(locked_event, room_id, user_auth_header)
        await _cancel_room_booking(old_booked_room, user_auth_header)
        return await _replace_booked_room(locked_event, new_booked_room)
    except Exception:
        if new_booked_room is not None:
            try:
                await _cancel_room_booking(new_booked_room, user_auth_header)
            except HTTPException:
                logger.warning("Failed to roll back newly created Room Booking reservation", exc_info=True)
        await _release_room_booking_lock(event)
        raise


async def _cancel_meeting_room(event: Event, user_auth_header: str) -> Event:
    await _require_room_booking_lock(
        event,
        require_unbooked=False,
        detail="Room booking is already being changed for this meeting",
    )

    try:
        locked_event = await _locked_event_with_booked_room(event)
        booked_room = cast(BookedRoom, locked_event.booked_room)
        await _cancel_room_booking(booked_room, user_auth_header)
        return await _replace_booked_room(locked_event, None)
    except Exception:
        await _release_room_booking_lock(event)
        raise


async def _cancel_room_before_delete(event: Event, user_auth_header: str) -> None:
    if event.booked_room is None:
        return

    await _require_room_booking_lock(
        event,
        require_unbooked=False,
        detail="Room booking is already being changed for this meeting",
    )

    try:
        locked_event = await Event.get(event.id)
        if locked_event is not None and locked_event.booked_room is not None:
            await _cancel_room_booking(locked_event.booked_room, user_auth_header)
    except Exception:
        await _release_room_booking_lock(event)
        raise


async def _get_meeting_or_404(meeting_ref: str) -> Event:
    event = await events_repo.read_by_ref(meeting_ref)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    return event


def _get_participant_or_404(event: Event, user_id: str) -> Participant:
    participant = next((p for p in event.participants if p.user_id == user_id), None)
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")
    return participant


def _ensure_owner(event: Event, user_id: str, action: str) -> None:
    if event.owner_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Only the owner can {action} the meeting",
        )


def _ensure_can_delete_participant(event: Event, participant: Participant, user_id: str) -> None:
    if event.owner_id == user_id or participant.user_id == user_id:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Only the owner or the participant themselves can remove this participant",
    )


@router.get(
    "/",
    responses={
        status.HTTP_200_OK: {"description": "List of meetings owned by the user"},
    },
)
async def get_my_meetings(auth: INH_TOKEN_AUTH) -> list[EventSummary]:
    """Get meetings owned by the authenticated user."""
    events = await events_repo.get_my_events(auth.innohassle_id)
    return [_event_summary(event) for event in events]


@router.post(
    "/",
    responses={
        status.HTTP_201_CREATED: {"description": "New meeting is created"},
    },
    status_code=status.HTTP_201_CREATED,
)
async def create_meeting(event_in: EventCreate, auth: INH_TOKEN_AUTH) -> EventView:
    """Create a new meeting with time slots."""
    event = await events_repo.create(event_in, owner_id=auth.innohassle_id)
    return await _event_view(event)


@router.get(
    "/participating",
    responses={
        status.HTTP_200_OK: {"description": "List of meetings where the user is a participant"},
    },
)
async def get_participating_meetings(auth: INH_TOKEN_AUTH) -> list[EventSummary]:
    """Get meetings where the authenticated user is a participant."""
    events = await events_repo.get_participating_events(auth.innohassle_id)
    return [_event_summary(event) for event in events]


@router.get(
    "/{meeting_ref}",
    responses={
        status.HTTP_200_OK: {"description": "Meeting info"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting not found"},
    },
)
async def get_meeting(meeting_ref: str, auth: INH_TOKEN_AUTH) -> EventView:
    """Get meeting details and participants' availability."""
    event = await _get_meeting_or_404(meeting_ref)
    return await _event_view(event)


@router.patch(
    "/{meeting_ref}",
    responses={
        status.HTTP_200_OK: {"description": "Meeting updated"},
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting not found"},
    },
)
async def update_meeting(
    meeting_ref: str,
    event_update: EventUpdate,
    auth: INH_TOKEN_AUTH,
    request: Request,
) -> EventView:
    """Update meeting details (owner only)."""
    event = await _get_meeting_or_404(meeting_ref)
    _ensure_owner(event, auth.innohassle_id, "update")

    changed_fields = event_update.model_fields_set
    updates_booking_time = "selected_time" in changed_fields and event_update.selected_time != event.selected_time
    updates_booking_title = "name" in changed_fields and event_update.name != event.name
    if event.booked_room is not None and (updates_booking_time or updates_booking_title):
        if event_update.selected_time is None and updates_booking_time:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot clear selected meeting time while a room is booked",
            )
        event = await _update_meeting_room_booking(
            event,
            event_update,
            updates_booking_time=updates_booking_time,
            updates_booking_title=updates_booking_title,
            user_auth_header=request.headers["authorization"],
        )
        return await _event_view(event)

    event = await events_repo.update_event(event, event_update)
    return await _event_view(event)


@router.delete(
    "/{meeting_ref}",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Meeting deleted"},
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting not found"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_meeting(meeting_ref: str, auth: INH_TOKEN_AUTH, request: Request) -> None:
    """Delete a meeting (owner only)."""
    event = await _get_meeting_or_404(meeting_ref)
    _ensure_owner(event, auth.innohassle_id, "delete")

    await _cancel_room_before_delete(event, request.headers["authorization"])
    await events_repo.delete_event(event)


@router.put(
    "/{meeting_ref}/participants",
    responses={
        status.HTTP_200_OK: {"description": "Participant availability updated"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting not found"},
    },
)
async def update_participant(
    meeting_ref: str,
    participant_in: ParticipantUpdate,
    auth: INH_TOKEN_AUTH,
) -> EventView:
    """Add or update a participant's availability for a meeting."""
    event = await _get_meeting_or_404(meeting_ref)

    event = await events_repo.update_participant(event, participant_in, user_id=auth.innohassle_id)
    return await _event_view(event)


@router.delete(
    "/{meeting_ref}/participants/{user_id}",
    responses={
        status.HTTP_200_OK: {"description": "Participant removed"},
        status.HTTP_403_FORBIDDEN: {"description": "Not allowed to remove this participant"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting or participant not found"},
    },
)
async def delete_participant(
    meeting_ref: str,
    user_id: str,
    auth: INH_TOKEN_AUTH,
) -> EventView:
    """Remove a participant from a meeting (owner or the participant themselves)."""
    event = await _get_meeting_or_404(meeting_ref)
    participant = _get_participant_or_404(event, user_id)
    _ensure_can_delete_participant(event, participant, auth.innohassle_id)

    event = await events_repo.delete_participant(event, user_id)
    return await _event_view(event)


@router.post(
    "/{meeting_ref}/book-room",
    responses={
        status.HTTP_200_OK: {"description": "Room booked for the meeting"},
        status.HTTP_400_BAD_REQUEST: {"description": "Selected meeting time is not set or room is unavailable"},
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner or room booking is forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting or room not found"},
        status.HTTP_409_CONFLICT: {"description": "Room is already booked for this meeting"},
    },
)
async def book_room_for_meeting(
    meeting_ref: str,
    request_body: BookRoomRequest,
    auth: INH_TOKEN_AUTH,
    request: Request,
) -> EventView:
    """Book a room for the meeting's selected time window (owner only)."""
    event = await _get_meeting_or_404(meeting_ref)
    _ensure_owner(event, auth.innohassle_id, "book a room for")
    if event.selected_time is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected meeting time is not set")
    if event.booked_room is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room is already booked for this meeting",
        )

    event = await _book_meeting_room(event, request_body.room_id, request.headers["authorization"])
    return await _event_view(event)


@router.patch(
    "/{meeting_ref}/book-room",
    responses={
        status.HTTP_200_OK: {"description": "Booked room changed for the meeting"},
        status.HTTP_400_BAD_REQUEST: {
            "description": "Room is not booked, selected time is not set, or room is unavailable"
        },
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner or room booking is forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting, booking, or room not found"},
        status.HTTP_409_CONFLICT: {"description": "Room booking is already being changed for this meeting"},
    },
)
async def change_room_for_meeting(
    meeting_ref: str,
    request_body: BookRoomRequest,
    auth: INH_TOKEN_AUTH,
    request: Request,
) -> EventView:
    """Change the booked room for a meeting (owner only)."""
    event = await _get_meeting_or_404(meeting_ref)
    _ensure_owner(event, auth.innohassle_id, "change the booked room for")
    if event.booked_room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room is not booked for this meeting")
    if event.selected_time is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected meeting time is not set")
    if event.booked_room.room_id == request_body.room_id:
        return await _event_view(event)

    event = await _change_meeting_room(event, request_body.room_id, request.headers["authorization"])
    return await _event_view(event)


@router.delete(
    "/{meeting_ref}/book-room",
    responses={
        status.HTTP_200_OK: {"description": "Booked room canceled for the meeting"},
        status.HTTP_400_BAD_REQUEST: {"description": "Room is not booked for this meeting"},
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner or room booking is forbidden"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting or booking not found"},
        status.HTTP_409_CONFLICT: {"description": "Room booking is already being changed for this meeting"},
    },
)
async def cancel_room_for_meeting(
    meeting_ref: str,
    auth: INH_TOKEN_AUTH,
    request: Request,
) -> EventView:
    """Cancel the booked room for a meeting (owner only)."""
    event = await _get_meeting_or_404(meeting_ref)
    _ensure_owner(event, auth.innohassle_id, "cancel the booked room for")
    if event.booked_room is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Room is not booked for this meeting")

    event = await _cancel_meeting_room(event, request.headers["authorization"])
    return await _event_view(event)


@router.get(
    "/{meeting_ref}/available-rooms",
    responses={
        status.HTTP_200_OK: {"description": "Rooms available for the selected meeting time"},
        status.HTTP_400_BAD_REQUEST: {"description": "Selected meeting time is not set"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting not found"},
    },
)
async def get_available_rooms(
    meeting_ref: str,
    auth: INH_TOKEN_AUTH,
    request: Request,
) -> list[AvailableRoom]:
    """Get rooms free for the meeting's selected time window."""
    event = await _get_meeting_or_404(meeting_ref)
    if event.selected_time is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected meeting time is not set")

    return await _get_available_rooms_for_time(
        start=event.selected_time.start,
        end=event.selected_time.end,
        user_auth_header=request.headers["authorization"],
    )
