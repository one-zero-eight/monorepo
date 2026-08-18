from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette.responses import Response

from src.dependencies import INH_TOKEN_AUTH
from src.events import repo as events_repo
from src.events.dependencies import ROLES
from src.events.ics import build_events_ics
from src.events.schemas import MeOut
from src.events.service import load_clubs_for_hosts, to_public_hosts

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/me")
async def get_me(auth: INH_TOKEN_AUTH, roles: ROLES) -> MeOut:
    """Get the current user's roles and owned clubs."""
    role_names: list[str] = []
    if roles.is_club_leader:
        role_names.append("club-leader")
    if roles.is_event_manager:
        role_names.append("event-manager")
    if roles.is_moderator:
        role_names.append("moderator")
    if roles.is_club_moderator:
        role_names.append("club-moderator")
    return MeOut(roles=role_names, clubs=roles.clubs)


@router.get("/me/events.ics")
async def get_my_enrolled_events_ics(auth: INH_TOKEN_AUTH) -> Response:
    """ICS feed of published events the current user is enrolled in."""
    events = await events_repo.list_published_enrolled_by_email(auth.email)
    published = [event for event in events if event.public is not None]
    all_hosts = [host for event in published if event.public for host in event.public.data.hosts]
    clubs = await load_clubs_for_hosts(all_hosts)
    hosts_by_event = {
        str(event.id): to_public_hosts(event.public.data.hosts, clubs)
        for event in published
        if event.public is not None
    }
    return Response(
        content=build_events_ics(published, hosts_by_event, f"{auth.email} Events schedule from innohassle.ru"),
        media_type="text/calendar",
    )
