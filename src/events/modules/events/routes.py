import datetime as dtm
from typing import Annotated

from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, Query
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette.responses import RedirectResponse

from src.dependencies import INH_TOKEN_AUTH, OPTIONAL_INH_TOKEN_AUTH
from src.events import repo as events_repo
from src.events.dependencies import MODERATOR_AUTH
from src.events.images_repo import images_repo
from src.events.mongo import Event, PublicEvent
from src.events.schemas import EventListItem, EventOut
from src.events.service import load_clubs_for_hosts, resolve_public_host, to_public_host, utcnow
from src.events.time_utils import TZAwareDateTime
from src.events.views import build_event_list_item, build_event_out

router = APIRouter(
    prefix="/events",
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
    clubs = await load_clubs_for_hosts([public.data.host for _, public in published])
    return [
        build_event_list_item(event, public, auth, to_public_host(public.data.host, clubs))
        for event, public in published
    ]


@router.get("/{id}")
async def get_event(id: PydanticObjectId, auth: OPTIONAL_INH_TOKEN_AUTH) -> EventOut:
    """Get a published event."""
    event, public = await _get_published_or_404(id)
    host = await resolve_public_host(public.data.host)
    return build_event_out(event, public, auth, host)


@router.post("/{id}/enroll")
async def enroll(id: PydanticObjectId, auth: INH_TOKEN_AUTH) -> EventOut:
    """Enroll the current user in the event."""
    event, public = await _get_published_or_404(id)
    if auth.innohassle_id not in public.enrolled_users:
        public.enrolled_users.append(auth.innohassle_id)
        await event.save()
    host = await resolve_public_host(public.data.host)
    return build_event_out(event, public, auth, host)


@router.post("/{id}/unenroll")
async def unenroll(id: PydanticObjectId, auth: INH_TOKEN_AUTH) -> EventOut:
    """Unenroll the current user from the event."""
    event, public = await _get_published_or_404(id)
    if auth.innohassle_id in public.enrolled_users:
        public.enrolled_users.remove(auth.innohassle_id)
        await event.save()
    host = await resolve_public_host(public.data.host)
    return build_event_out(event, public, auth, host)


@router.delete("/{id}")
async def unpublish_event(id: PydanticObjectId, _: MODERATOR_AUTH) -> None:
    """Unpublish the event by erasing its public data (moderator only)."""
    event, _public = await _get_published_or_404(id)
    event.public = None
    await event.save()


@router.get("/{id}/image")
async def get_event_image(id: PydanticObjectId) -> RedirectResponse:
    """Redirect to the event image in MinIO."""
    _, public = await _get_published_or_404(id)
    image_id = public.data.image_id
    if not image_id:
        raise HTTPException(status_code=404, detail="No image available")
    return RedirectResponse(url=images_repo.get_url(image_id))
