import datetime as dtm
import re
import secrets

from beanie import PydanticObjectId

from src.when2meet.mongo import Event, Participant

from .archive import calculate_archive_after
from .schemas import EventCreate, EventUpdate, MeetingStatus, ParticipantUpdate

OBJECT_ID_RE = re.compile(r"^[0-9a-f]{24}$")
SLUG_BYTES = 6


async def generate_unique_slug() -> str:
    """Generate a short unique event slug."""
    while True:
        slug = secrets.token_urlsafe(SLUG_BYTES)
        if await Event.find_one(Event.slug == slug) is None:
            return slug


async def create(data: EventCreate, owner_id: str | None = None) -> Event:
    """Create a new event."""
    event = Event(
        **data.model_dump(),
        owner_id=owner_id,
        slug=await generate_unique_slug(),
        archive_after=calculate_archive_after(data.slots, selected_time=None),
    )
    return await event.insert()


async def read(event_id: PydanticObjectId) -> Event | None:
    """Get event by ID."""
    return await Event.get(event_id)


async def read_by_ref(event_ref: str) -> Event | None:
    """Get event by ObjectId or slug."""
    if OBJECT_ID_RE.fullmatch(event_ref):
        return await Event.get(PydanticObjectId(event_ref))
    return await Event.find_one(Event.slug == event_ref)


def _find_participant(event: Event, user_id: str) -> Participant | None:
    return next((participant for participant in event.participants if participant.user_id == user_id), None)


def _merge_availability_with_hidden_slots(
    existing_availability: list[dtm.datetime],
    new_availability: list[dtm.datetime],
    visible_slots: list[dtm.datetime],
) -> list[dtm.datetime]:
    visible_slots_set = set(visible_slots)
    hidden_availability = [slot for slot in existing_availability if slot not in visible_slots_set]
    return list(dict.fromkeys(hidden_availability + new_availability))


async def update_participant(event: Event, data: ParticipantUpdate, user_id: str) -> Event:
    """Update or add participant availability."""
    participant = _find_participant(event, user_id)
    if participant:
        participant.availability = _merge_availability_with_hidden_slots(
            existing_availability=participant.availability,
            new_availability=data.availability,
            visible_slots=event.slots,
        )
    else:
        event.participants.append(Participant(user_id=user_id, availability=data.availability))

    return await event.save()


def _status_filter(meeting_status: MeetingStatus, now: dtm.datetime) -> dict[str, object]:
    if meeting_status == MeetingStatus.ACTIVE:
        return {
            "manually_archived_at": None,
            "archive_after": {"$gt": now},
        }
    return {
        "$or": [
            {"manually_archived_at": {"$exists": True}},
            {"archive_after": {"$lte": now}},
        ]
    }


async def get_my_events(owner_id: str, meeting_status: MeetingStatus, now: dtm.datetime) -> list[Event]:
    """Get events owned by the user."""
    return (
        await Event.find(Event.owner_id == owner_id, _status_filter(meeting_status, now)).sort("-created_at").to_list()
    )


async def get_participating_events(
    user_id: str,
    meeting_status: MeetingStatus,
    now: dtm.datetime,
) -> list[Event]:
    """Get events where the user is a participant but not the owner."""
    return (
        await Event.find(
            {"participants.user_id": user_id, "owner_id": {"$ne": user_id}},
            _status_filter(meeting_status, now),
        )
        .sort("-created_at")
        .to_list()
    )


async def update_event(event: Event, data: EventUpdate) -> Event:
    """Update event details."""
    for field_name in data.model_fields_set:
        setattr(event, field_name, getattr(data, field_name))
    event.archive_after = calculate_archive_after(event.slots, event.selected_time)
    return await event.save()


async def archive_event(event: Event, archived_at: dtm.datetime) -> Event:
    """Manually archive an active event."""
    event.manually_archived_at = archived_at
    return await event.save()


async def delete_event(event: Event) -> None:
    """Delete an event."""
    await event.delete()


async def delete_participant(event: Event, user_id: str) -> Event:
    """Remove a participant from an event."""
    event.participants = [p for p in event.participants if p.user_id != user_id]
    return await event.save()
