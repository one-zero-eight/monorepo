import datetime as dtm
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette.responses import RedirectResponse, Response

from src.dependencies import INH_TOKEN_AUTH, OPTIONAL_INH_TOKEN_AUTH
from src.events import repo as events_repo
from src.events.dependencies import MODERATOR_AUTH, OPTIONAL_ROLES, ROLES
from src.events.ics import build_events_ics
from src.events.images_repo import images_repo
from src.events.mongo import EnrollmentType, Event, PublicEvent
from src.events.schemas import EventListItem, EventOut
from src.events.service import load_clubs_for_hosts, resolve_public_hosts, to_public_hosts, utcnow
from src.events.time_utils import TZAwareDateTime
from src.events.views import build_event_list_item, build_event_out

router = APIRouter(
    prefix="/events",
    tags=["Events"],
    route_class=AutoDeriveResponsesAPIRoute,
)

ics_router = APIRouter(
    tags=["Events"],
    route_class=AutoDeriveResponsesAPIRoute,
)


async def _get_published_or_404(id: PydanticObjectId) -> tuple[Event, PublicEvent]:
    event = await events_repo.get(id)
    if event is None or event.public is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event, event.public


@router.get("/")
async def list_events(
    from_: Annotated[TZAwareDateTime | None, Query(alias="from")] = None,
    to_: Annotated[TZAwareDateTime | None, Query(alias="to")] = None,
    auth: OPTIONAL_INH_TOKEN_AUTH = None,
) -> list[EventListItem]:
    """List published events; defaults to the current month window."""
    now = utcnow()
    from_dt = from_ if from_ is not None else now
    to_dt = to_ if to_ is not None else now + dtm.timedelta(days=30)
    if from_dt > to_dt:
        raise HTTPException(status_code=400, detail="from must not be later than to")
    events = await events_repo.list_published(from_dt, to_dt)
    published = [(event, event.public) for event in events if event.public is not None]
    all_hosts = [host for _, public in published for host in public.data.hosts]
    clubs = await load_clubs_for_hosts(all_hosts)
    return [
        build_event_list_item(event, public, auth, to_public_hosts(public.data.hosts, clubs))
        for event, public in published
    ]


@ics_router.get("/events.ics")
async def get_events_ics() -> Response:
    """ICS feed of all published events (no event description, no enrollment filtering)."""
    events = await events_repo.list_all_published()
    published = [event for event in events if event.public is not None]
    all_hosts = [host for event in published if event.public for host in event.public.data.hosts]
    clubs = await load_clubs_for_hosts(all_hosts)
    hosts_by_event = {
        str(event.id): to_public_hosts(event.public.data.hosts, clubs)
        for event in published
        if event.public is not None
    }
    return Response(
        content=build_events_ics(published, hosts_by_event, "Events from innohassle.ru"),
        media_type="text/calendar",
    )


@router.get("/{id}")
async def get_event(id: PydanticObjectId, auth: OPTIONAL_INH_TOKEN_AUTH, roles: OPTIONAL_ROLES) -> EventOut:
    """Get a published event."""
    event, public = await _get_published_or_404(id)
    hosts = await resolve_public_hosts(public.data.hosts)
    return build_event_out(event, public, auth, hosts, roles=roles)


@router.post("/{id}/enroll")
async def enroll(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> EventOut:
    """Enroll the current user in the event (stores email)."""
    event, public = await _get_published_or_404(id)
    enrollment = public.data.enrollment
    if (
        enrollment.type == EnrollmentType.INTERNAL
        and enrollment.capacity is not None
        and auth.email not in public.enrolled_emails
        and len(public.enrolled_emails) >= enrollment.capacity
    ):
        raise HTTPException(status_code=400, detail="Event is at capacity")
    if auth.email not in public.enrolled_emails:
        public.enrolled_emails.append(auth.email)
        await event.save()
    hosts = await resolve_public_hosts(public.data.hosts)
    return build_event_out(event, public, auth, hosts, roles=roles)


@router.post("/{id}/unenroll")
async def unenroll(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> EventOut:
    """Unenroll the current user from the event."""
    event, public = await _get_published_or_404(id)
    if auth.email in public.enrolled_emails:
        public.enrolled_emails.remove(auth.email)
        await event.save()
    hosts = await resolve_public_hosts(public.data.hosts)
    return build_event_out(event, public, auth, hosts, roles=roles)


@router.delete("/{id}")
async def unpublish_event(id: PydanticObjectId, _: MODERATOR_AUTH) -> None:
    """Unpublish the event by erasing its public data (moderator only)."""
    event, _public = await _get_published_or_404(id)
    event.public = None
    await event.save()


@router.get("/{id}/image")
async def get_event_image(id: PydanticObjectId) -> RedirectResponse:
    """Redirect to the event image in MinIO (public; for <img src>)."""
    _, public = await _get_published_or_404(id)
    image_id = public.data.image_id
    if not image_id:
        raise HTTPException(status_code=404, detail="No image available")
    return RedirectResponse(url=images_repo.get_url(image_id))
