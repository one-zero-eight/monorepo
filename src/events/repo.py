import datetime as dtm

from beanie import PydanticObjectId

from src.events.mongo import Draft, Event, EventData, HostType
from src.events.service import utcnow


async def create(creator_id: str, data: EventData) -> Event:
    return await Event(
        creator_id=creator_id,
        invitations=[],
        draft=Draft(revision=utcnow(), data=data),
    ).create()


async def get(id: PydanticObjectId) -> Event | None:
    return await Event.get(id)


async def list_by_creator(creator_id: str) -> list[Event]:
    return await Event.find(Event.creator_id == creator_id).to_list()


async def list_accessible_drafts(creator_id: str, club_ids: list[str]) -> list[Event]:
    """Drafts the user created, co-hosts, or has a pending invitation for."""
    clauses: list[dict] = [{"creator_id": creator_id}]
    if club_ids:
        clauses.append({"invitations": {"$in": club_ids}})
        clauses.append({"draft.data.hosts": {"$elemMatch": {"type": HostType.CLUB, "club_id": {"$in": club_ids}}}})
    return await Event.find({"$or": clauses}).to_list()


async def list_with_submission() -> list[Event]:
    return await Event.find({"submission": {"$ne": None}}).to_list()


async def list_with_submission_by_creator(creator_id: str) -> list[Event]:
    return await Event.find({"creator_id": creator_id, "submission": {"$ne": None}}).to_list()


async def list_published(from_dt: dtm.datetime, to_dt: dtm.datetime) -> list[Event]:
    return await Event.find(
        {"public": {"$ne": None}, "public.data.starts_at": {"$gte": from_dt, "$lte": to_dt}}
    ).to_list()


async def list_all_published() -> list[Event]:
    return await Event.find({"public": {"$ne": None}}).to_list()


async def list_published_enrolled_by_email(email: str) -> list[Event]:
    return await Event.find({"public": {"$ne": None}, "public.enrolled_emails": email}).to_list()
