import datetime as dtm
from typing import cast

import httpx
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
    EventCreate,
    EventSummary,
    EventUpdate,
    EventView,
    ParticipantUpdate,
    ParticipantView,
    RoomBookingBooking,
    RoomBookingCanBook,
    RoomBookingRoom,
)

router = APIRouter(
    prefix="/meetings",
    tags=["Meetings"],
    route_class=AutoDeriveResponsesAPIRoute,
)

type RoomBookingQueryParams = dict[str, str] | list[tuple[str, str | int | float | None]]


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
        **event.model_dump(exclude={"participants"}),
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


async def _room_booking_get(path: str, params: RoomBookingQueryParams, user_auth_header: str) -> object:
    room_booking_settings = settings.room_booking
    if room_booking_settings is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Room Booking integration is not configured",
        )

    url = f"{room_booking_settings.api_url.rstrip('/')}/{path.lstrip('/')}"
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

    try:
        return response.json()
    except ValueError as exc:
        logger.warning("Room Booking API returned invalid JSON", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Room Booking API returned an invalid response",
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


async def _can_book_room(room_id: str, start: dtm.datetime, end: dtm.datetime, user_auth_header: str) -> bool:
    params = {
        "start": start.isoformat(),
        "end": end.isoformat(),
    }
    can_book = await _room_booking_get(f"/room/{room_id}/can-book", params=params, user_auth_header=user_auth_header)
    return RoomBookingCanBook.model_validate(can_book).can_book


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
) -> EventView:
    """Update meeting details (owner only)."""
    event = await _get_meeting_or_404(meeting_ref)
    _ensure_owner(event, auth.innohassle_id, "update")

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
async def delete_meeting(meeting_ref: str, auth: INH_TOKEN_AUTH) -> None:
    """Delete a meeting (owner only)."""
    event = await _get_meeting_or_404(meeting_ref)
    _ensure_owner(event, auth.innohassle_id, "delete")

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


@router.get(
    "/{meeting_id}/available-rooms",
    responses={
        status.HTTP_200_OK: {"description": "Rooms available for the selected meeting time"},
        status.HTTP_400_BAD_REQUEST: {"description": "Selected meeting time is not set"},
        status.HTTP_404_NOT_FOUND: {"description": "Meeting not found"},
    },
)
async def get_available_rooms(
    meeting_id: str,
    auth: INH_TOKEN_AUTH,
    request: Request,
) -> list[AvailableRoom]:
    """Get rooms free for the meeting's selected time window."""
    event = await _get_meeting_or_404(meeting_id)
    if event.selected_time is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected meeting time is not set")

    user_auth_header = request.headers["authorization"]
    rooms = await _get_rooms(user_auth_header)
    bookings = await _get_room_bookings(
        room_ids=[room.id for room in rooms],
        start=event.selected_time.start,
        end=event.selected_time.end,
        user_auth_header=user_auth_header,
    )
    busy_room_ids = {
        booking.room_id
        for booking in bookings
        if _booking_overlaps(booking, event.selected_time.start, event.selected_time.end)
    }

    free_rooms = [room for room in rooms if room.id not in busy_room_ids]

    import asyncio

    can_book_flags = await asyncio.gather(
        *[
            _can_book_room(room.id, event.selected_time.start, event.selected_time.end, user_auth_header)
            for room in free_rooms
        ]
    )
    available_rooms = [room for room, can_book in zip(free_rooms, can_book_flags) if can_book]
    return [_room_view(room) for room in available_rooms]
