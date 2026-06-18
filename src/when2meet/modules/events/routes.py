from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, status
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.dependencies import INH_TOKEN_AUTH
from src.when2meet.mongo import Event

from . import events_repo
from .schemas import EventCreate, EventSummary, EventUpdate, ParticipantUpdate

router = APIRouter(
    prefix="/events",
    tags=["Events"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get(
    "/",
    responses={
        status.HTTP_200_OK: {"description": "List of events matching the query"},
    },
)
async def search_events(q: str, auth: INH_TOKEN_AUTH) -> list[EventSummary]:
    """Search for events by name or description."""
    events = await events_repo.search(q)
    return [
        EventSummary(
            **e.model_dump(include={"id", "name", "description", "created_at"}),
            participants_count=len(e.participants),
        )
        for e in events
    ]


@router.post(
    "/",
    responses={
        status.HTTP_201_CREATED: {"description": "New event is created"},
    },
    status_code=status.HTTP_201_CREATED,
)
async def create_event(event_in: EventCreate, auth: INH_TOKEN_AUTH) -> Event:
    """Create a new event with time slots."""
    return await events_repo.create(event_in, owner_id=auth.innohassle_id)


@router.get(
    "/mine",
    responses={
        status.HTTP_200_OK: {"description": "List of events owned by the user"},
    },
)
async def get_my_events(auth: INH_TOKEN_AUTH) -> list[EventSummary]:
    """Get events owned by the authenticated user."""
    events = await events_repo.get_my_events(auth.innohassle_id)
    return [
        EventSummary(
            **e.model_dump(include={"id", "name", "description", "created_at"}),
            participants_count=len(e.participants),
        )
        for e in events
    ]


@router.get(
    "/participating",
    responses={
        status.HTTP_200_OK: {"description": "List of events where the user is a participant"},
    },
)
async def get_participating_events(auth: INH_TOKEN_AUTH) -> list[EventSummary]:
    """Get events where the authenticated user is a participant."""
    events = await events_repo.get_participating_events(auth.innohassle_id)
    return [
        EventSummary(
            **e.model_dump(include={"id", "name", "description", "created_at"}),
            participants_count=len(e.participants),
        )
        for e in events
    ]


@router.get(
    "/{event_id}",
    responses={
        status.HTTP_200_OK: {"description": "Event info"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
)
async def get_event(event_id: PydanticObjectId, auth: INH_TOKEN_AUTH) -> Event:
    """Get event details and participants' availability."""
    event = await events_repo.read(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return event


@router.patch(
    "/{event_id}",
    responses={
        status.HTTP_200_OK: {"description": "Event updated"},
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
)
async def update_event(
    event_id: PydanticObjectId,
    event_update: EventUpdate,
    auth: INH_TOKEN_AUTH,
) -> Event:
    """Update event details (owner only)."""
    event = await events_repo.read(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if event.owner_id != auth.innohassle_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can update the event",
        )

    if event_update.slots is not None:
        new_slots_set = set(event_update.slots)
        for p in event.participants:
            for slot in p.availability:
                if slot not in new_slots_set:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Participant {p.name} has availability at {slot} which is not in the new slots",
                    )
            for slot in p.if_needed:
                if slot not in new_slots_set:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Participant {p.name} has 'if_needed' at {slot} which is not in the new slots",
                    )

    return await events_repo.update_event(event, event_update)


@router.delete(
    "/{event_id}",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Event deleted"},
        status.HTTP_403_FORBIDDEN: {"description": "Not an owner"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_event(event_id: PydanticObjectId, auth: INH_TOKEN_AUTH):
    """Delete an event (owner only)."""
    event = await events_repo.read(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    if event.owner_id != auth.innohassle_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete the event",
        )

    await events_repo.delete_event(event)


@router.put(
    "/{event_id}/participants",
    responses={
        status.HTTP_200_OK: {"description": "Participant availability updated"},
        status.HTTP_400_BAD_REQUEST: {"description": "Invalid availability slots"},
        status.HTTP_404_NOT_FOUND: {"description": "Event not found"},
    },
)
async def update_participant(
    event_id: PydanticObjectId,
    participant_in: ParticipantUpdate,
    auth: INH_TOKEN_AUTH,
) -> Event:
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

    if participant_in.if_needed:
        for slot in participant_in.if_needed:
            if slot not in event_slots_set:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Slot {slot} (if_needed) is not available for this event",
                )
            if slot in participant_in.availability:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Slot {slot} cannot be both available and if_needed",
                )

    return await events_repo.update_participant(event, participant_in, user_id=auth.innohassle_id)


@router.delete(
    "/{event_id}/participants/{name}",
    responses={
        status.HTTP_200_OK: {"description": "Participant removed"},
        status.HTTP_403_FORBIDDEN: {"description": "Not allowed to remove this participant"},
        status.HTTP_404_NOT_FOUND: {"description": "Event or participant not found"},
    },
)
async def delete_participant(
    event_id: PydanticObjectId,
    name: str,
    auth: INH_TOKEN_AUTH,
) -> Event:
    """Remove a participant from an event (owner or the participant themselves)."""
    event = await events_repo.read(event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    participant = next((p for p in event.participants if p.name == name), None)
    if not participant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Participant not found")

    # Access control: owner can delete anyone; participant can delete themselves (if user_id matches)
    is_owner = event.owner_id == auth.innohassle_id
    is_self = participant.user_id == auth.innohassle_id

    if not (is_owner or is_self):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner or the participant themselves can remove this participant",
        )

    return await events_repo.delete_participant(event, name)
