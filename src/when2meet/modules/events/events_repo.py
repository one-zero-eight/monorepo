from beanie import PydanticObjectId

from src.when2meet.mongo import Event, Participant

from .schemas import EventCreate, EventUpdate, ParticipantUpdate


async def create(data: EventCreate, owner_id: str | None = None) -> Event:
    """Create a new event."""
    event = Event(**data.model_dump(), owner_id=owner_id)
    return await event.insert()


async def read(event_id: PydanticObjectId) -> Event | None:
    """Get event by ID."""
    return await Event.get(event_id)


async def update_participant(event: Event, data: ParticipantUpdate, user_id: str | None = None) -> Event:
    """Update or add participant availability."""
    participant_found = False
    for p in event.participants:
        if p.name == data.name:
            p.availability = data.availability
            if data.if_needed is not None:
                p.if_needed = data.if_needed
            if user_id:
                p.user_id = user_id
            participant_found = True
            break

    if not participant_found:
        participant_data = data.model_dump()
        if data.if_needed is None:
            participant_data["if_needed"] = []
        event.participants.append(Participant(**participant_data, user_id=user_id))

    return await event.save()


async def get_my_events(owner_id: str) -> list[Event]:
    """Get events owned by the user."""
    return await Event.find(Event.owner_id == owner_id).sort("-created_at").to_list()


async def get_participating_events(user_id: str) -> list[Event]:
    """Get events where the user is a participant but not the owner."""
    return (
        await Event.find(
            {"participants.user_id": user_id, "owner_id": {"$ne": user_id}},
        )
        .sort("-created_at")
        .to_list()
    )


async def update_event(event: Event, data: EventUpdate) -> Event:
    """Update event details."""
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(event, key, value)
    return await event.save()


async def delete_event(event: Event):
    """Delete an event."""
    await event.delete()


async def delete_participant(event: Event, participant_name: str) -> Event:
    """Remove a participant from an event."""
    event.participants = [p for p in event.participants if p.name != participant_name]
    return await event.save()


async def search(query: str, limit: int = 20) -> list[Event]:
    """Search for events using text index with relevance sorting."""
    return (
        await Event.find({"$text": {"$search": query}}).sort([("score", {"$meta": "textScore"})]).limit(limit).to_list()
    )
