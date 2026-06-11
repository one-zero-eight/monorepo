from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, status
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.when2meet.mongo import Event

from . import events_repo
from .schemas import EventCreate, ParticipantUpdate

router = APIRouter(
    prefix="/events",
    tags=["Events"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.post(
    "/",
    responses={
        status.HTTP_201_CREATED: {"description": "New event is created"},
    },
    status_code=status.HTTP_201_CREATED,
)
async def create_event(event_in: EventCreate) -> Event:
    """Create a new event with time slots."""
    return await events_repo.create(event_in)


@router.get(
    "/{event_id}",
    responses={
        status.HTTP_200_OK: {"description": "Event info"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
)
async def get_event(event_id: PydanticObjectId) -> Event:
    """Get event details and participants' availability."""
    event = await events_repo.read(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.put(
    "/{event_id}/participants",
    responses={
        status.HTTP_200_OK: {"description": "Participant availability updated"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid availability slots"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
)
async def update_participant(event_id: PydanticObjectId, participant_in: ParticipantUpdate) -> Event:
    """Add or update a participant's availability for an event."""
    event = await events_repo.read(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    event_slots_set = set(event.slots)
    for slot in participant_in.availability:
        if slot not in event_slots_set:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Slot {slot} is not available for this event",
            )

    return await events_repo.update_participant(event, participant_in)
