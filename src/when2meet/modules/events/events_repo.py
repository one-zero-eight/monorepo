from beanie import PydanticObjectId

from src.when2meet.mongo import Event, Participant

from .schemas import EventCreate, ParticipantUpdate


async def create(data: EventCreate) -> Event:
    """Create a new event."""
    event = Event(**data.model_dump())
    return await event.insert()


async def read(event_id: PydanticObjectId) -> Event | None:
    """Get event by ID."""
    return await Event.get(event_id)


async def update_participant(event: Event, data: ParticipantUpdate) -> Event:
    """Update or add participant availability."""
    participant_found = False
    for p in event.participants:
        if p.name == data.name:
            p.availability = data.availability
            participant_found = True
            break

    if not participant_found:
        event.participants.append(Participant(**data.model_dump()))

    return await event.save()
