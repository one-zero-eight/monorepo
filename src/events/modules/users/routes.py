from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette.responses import Response

from src.dependencies import INH_TOKEN_AUTH
from src.events import repo as events_repo
from src.events.dependencies import ROLES, ScheduleApiKeyDep
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


@router.get(
    "/me/events.ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {"schema": {"type": "string"}}}}},
)
async def get_my_enrolled_events_ics(auth: INH_TOKEN_AUTH) -> Response:
    """ICS feed of published events the current user is enrolled in."""
    return await _enrolled_events_ics(auth.email)


@router.get(
    "/integrations/schedule/{email}/events.ics",
    response_class=Response,
    responses={
        200: {"content": {"text/calendar": {"schema": {"type": "string"}}}},
        401: {
            "description": "Invalid service API key",
            "headers": {"WWW-Authenticate": {"schema": {"type": "string"}}},
        },
        503: {"description": "Schedule integration is not configured"},
    },
)
async def get_schedule_user_events_ics(email: str, _: ScheduleApiKeyDep) -> Response:
    """Service-key protected enrolled-events feed for Schedule access-key subscriptions.

    The key is configured with ``events_service.api_key`` and must be shared only
    with Schedule. The integration is disabled with 503 when no key is configured.
    No user JWT or enrollment identities are exposed by this endpoint.
    """
    return await _enrolled_events_ics(email)


async def _enrolled_events_ics(email: str) -> Response:
    events = await events_repo.list_published_enrolled_by_email(email)
    published = [event for event in events if event.public is not None]
    all_hosts = [host for event in published if event.public for host in event.public.data.hosts]
    clubs = await load_clubs_for_hosts(all_hosts)
    hosts_by_event = {
        str(event.id): to_public_hosts(event.public.data.hosts, clubs)
        for event in published
        if event.public is not None
    }
    return Response(
        content=build_events_ics(published, hosts_by_event, f"{email} Events schedule from innohassle.ru"),
        media_type="text/calendar",
    )
