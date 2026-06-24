import re
import secrets

from beanie import PydanticObjectId

from src.when2meet.mongo import Event, Participant

from .schemas import EventCreate, EventUpdate, ParticipantUpdate

OBJECT_ID_RE = re.compile(r"^[0-9a-f]{24}$")


async def generate_unique_slug() -> str:
    """Generate a short unique event slug."""
    while True:
        slug = secrets.token_urlsafe(6)
        if await Event.find_one(Event.slug == slug) is None:
            return slug


async def create(data: EventCreate, owner_id: str | None = None) -> Event:
    """Create a new event."""
    event = Event(**data.model_dump(), owner_id=owner_id, slug=await generate_unique_slug())
    return await event.insert()


async def read(event_id: PydanticObjectId) -> Event | None:
    """Get event by ID."""
    return await Event.get(event_id)


async def read_by_ref(event_ref: str) -> Event | None:
    """Get event by ObjectId or slug."""
    if OBJECT_ID_RE.fullmatch(event_ref):
        return await Event.get(PydanticObjectId(event_ref))
    return await Event.find_one(Event.slug == event_ref)


async def update_participant(event: Event, data: ParticipantUpdate, user_id: str) -> Event:
    """Update or add participant availability."""
    for p in event.participants:
        if p.user_id == user_id:
            p.availability = data.availability
            break
    else:
        event.participants.append(Participant(user_id=user_id, availability=data.availability))

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


async def delete_participant(event: Event, user_id: str) -> Event:
    """Remove a participant from an event."""
    event.participants = [p for p in event.participants if p.user_id != user_id]
    return await event.save()
