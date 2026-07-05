import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import ValidationError

from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import UserSchema, inh_accounts
from src.logging_ import logger
from src.when2meet.mongo import Event, Participant

from . import events_repo
from .schemas import EventCreate, EventSummary, EventUpdate, EventView, ParticipantUpdate, ParticipantView

router = APIRouter(
    prefix="/events",
    tags=["Events"],
    route_class=AutoDeriveResponsesAPIRoute,
)


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
        **event.model_dump(include={"id", "slug", "name", "description", "created_at"}),
        participants_count=len(event.participants),
    )


async def _get_event_or_404(event_ref: str) -> Event:
    event = await events_repo.read_by_ref(event_ref)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
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
            detail=f"Only the owner can {action} the event",
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
        status.HTTP_200_OK: {"description": "List of events owned by the user"},
    },
)
async def get_my_events(auth: INH_TOKEN_AUTH) -> list[EventSummary]:
    """Get events owned by the authenticated user."""
    events = await events_repo.get_my_events(auth.innohassle_id)
    return [_event_summary(event) for event in events]


@router.post(
    "/",
    responses={
        status.HTTP_201_CREATED: {"description": "New event is created"},
    },
    status_code=status.HTTP_201_CREATED,
)
async def create_event(event_in: EventCreate, auth: INH_TOKEN_AUTH) -> EventView:
    """Create a new event with time slots."""
    event = await events_repo.create(event_in, owner_id=auth.innohassle_id)
    return await _event_view(event)


@router.get(
    "/participating",
    responses={
        status.HTTP_200_OK: {"description": "List of events where the user is a participant"},
    },
)
async def get_participating_events(auth: INH_TOKEN_AUTH) -> list[EventSummary]:
    """Get events where the authenticated user is a participant."""
    events = await events_repo.get_participating_events(auth.innohassle_id)
    return [_event_summary(event) for event in events]


@router.get(
    "/{event_ref}",
    responses={
        status.HTTP_200_OK: {"description": "Event info"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
)
async def get_event(event_ref: str, auth: INH_TOKEN_AUTH) -> EventView:
    """Get event details and participants' availability."""
    event = await _get_event_or_404(event_ref)
    return await _event_view(event)


@router.patch(
    "/{event_ref}",
    responses={
        status.HTTP_200_OK: {"description": "Event updated"},
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
)
async def update_event(
    event_ref: str,
    event_update: EventUpdate,
    auth: INH_TOKEN_AUTH,
) -> EventView:
    """Update event details (owner only)."""
    event = await _get_event_or_404(event_ref)
    _ensure_owner(event, auth.innohassle_id, "update")

    event = await events_repo.update_event(event, event_update)
    return await _event_view(event)


@router.delete(
    "/{event_ref}",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Event deleted"},
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_event(event_ref: str, auth: INH_TOKEN_AUTH) -> None:
    """Delete an event (owner only)."""
    event = await _get_event_or_404(event_ref)
    _ensure_owner(event, auth.innohassle_id, "delete")

    await events_repo.delete_event(event)


@router.put(
    "/{event_ref}/participants",
    responses={
        status.HTTP_200_OK: {"description": "Participant availability updated"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
)
async def update_participant(
    event_ref: str,
    participant_in: ParticipantUpdate,
    auth: INH_TOKEN_AUTH,
) -> EventView:
    """Add or update a participant's availability for an event."""
    event = await _get_event_or_404(event_ref)

    event = await events_repo.update_participant(event, participant_in, user_id=auth.innohassle_id)
    return await _event_view(event)


@router.delete(
    "/{event_ref}/participants/{user_id}",
    responses={
        status.HTTP_200_OK: {"description": "Participant removed"},
        status.HTTP_403_FORBIDDEN: {"description": "Not allowed to remove this participant"},
        status.HTTP_404_NOT_FOUND: {"description": "Event or participant not found"},
    },
)
async def delete_participant(
    event_ref: str,
    user_id: str,
    auth: INH_TOKEN_AUTH,
) -> EventView:
    """Remove a participant from an event (owner or the participant themselves)."""
    event = await _get_event_or_404(event_ref)
    participant = _get_participant_or_404(event, user_id)
    _ensure_can_delete_participant(event, participant, auth.innohassle_id)

    event = await events_repo.delete_participant(event, user_id)
    return await _event_view(event)
