from io import BytesIO

import filetype
from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from PIL import Image
from starlette.responses import RedirectResponse

from src.dependencies import INH_TOKEN_AUTH
from src.events import repo as events_repo
from src.events.config import settings
from src.events.dependencies import ROLES
from src.events.images_repo import images_repo
from src.events.mongo import EventData, EventLink, Host, HostType, Locale, ModerationStatus
from src.events.schemas import (
    AddClubHostBody,
    AddExternalHostBody,
    AddLinkBody,
    CreateDraft,
    DraftListItem,
    DraftOut,
    ImageUploadResponse,
    InviteClubBody,
    OrderHostsBody,
    PatchDraft,
    PatchExternalHostBody,
    PatchLinkBody,
    PutLocale,
    RestoreBody,
)
from src.events.service import (
    get_editable_draft,
    get_viewable_draft,
    is_pending_invitee,
    new_host_id,
    new_link_id,
    owned_club_ids,
    resolve_invited_by_name,
    utcnow,
)
from src.events.views import build_draft_list_item, build_draft_out

router = APIRouter(
    prefix="/drafts",
    tags=["Drafts"],
    route_class=AutoDeriveResponsesAPIRoute,
)


def _validate_locale_codes(codes: list[str]) -> None:
    allowed = set(settings.locales)
    for code in codes:
        if code not in allowed:
            raise HTTPException(
                status_code=400, detail=f"Locale {code!r} is not in the allowed list: {settings.locales}"
            )


def _find_host(hosts: list[Host], host_id: str) -> Host | None:
    for host in hosts:
        if host.id == host_id:
            return host
    return None


@router.post("/")
async def create_draft(body: CreateDraft, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Create a draft event."""
    if not roles.is_club_leader and not roles.is_event_manager:
        raise HTTPException(status_code=403, detail="Only club leaders or event managers can create drafts")
    _validate_locale_codes(body.locales or [])
    data = EventData(
        starts_at=body.starts_at,
        location=body.location,
        locales={code: Locale() for code in body.locales or []},
        duration_hours=body.duration_hours,
        enrollment=body.enrollment,
    )
    event = await events_repo.create(auth.innohassle_id, data)
    return build_draft_out(event, roles)


@router.get("/")
async def list_drafts(auth: INH_TOKEN_AUTH, roles: ROLES) -> list[DraftListItem]:
    """List drafts the user created, co-hosts, or was invited to."""
    club_ids = list(owned_club_ids(roles))
    events = await events_repo.list_accessible_drafts(auth.innohassle_id, club_ids)
    items: list[DraftListItem] = []
    for event in events:
        invited_by = None
        if is_pending_invitee(event, roles):
            invited_by = await resolve_invited_by_name(event.creator_id)
        items.append(build_draft_list_item(event, invited_by=invited_by))
    return items


@router.get("/{id}")
async def get_draft(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Get a draft the user can view."""
    event = await get_viewable_draft(id, roles)
    return build_draft_out(event, roles)


@router.patch("/{id}")
async def patch_draft(id: PydanticObjectId, body: PatchDraft, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Change draft data (starts_at / location / duration / enrollment)."""
    event = await get_editable_draft(id, roles)
    if "starts_at" in body.model_fields_set:
        event.draft.data.starts_at = body.starts_at
    if "location" in body.model_fields_set:
        event.draft.data.location = body.location
    if "duration_hours" in body.model_fields_set:
        event.draft.data.duration_hours = body.duration_hours
    if "enrollment" in body.model_fields_set:
        event.draft.data.enrollment = body.enrollment
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.put("/{id}/locales/{locale}")
async def put_locale(
    id: PydanticObjectId, locale: str, body: PutLocale, auth: INH_TOKEN_AUTH, roles: ROLES
) -> DraftOut:
    """Replace name and description in a locale; auto-creates the locale if missing."""
    event = await get_editable_draft(id, roles)
    _validate_locale_codes([locale])
    event.draft.data.locales[locale] = Locale(name=body.name, description=body.description)
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.delete("/{id}/locales/{locale}")
async def delete_locale(id: PydanticObjectId, locale: str, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Delete a locale from the draft."""
    event = await get_editable_draft(id, roles)
    _validate_locale_codes([locale])
    event.draft.data.locales.pop(locale, None)
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.post("/{id}/hosts/external")
async def add_external_host(
    id: PydanticObjectId, body: AddExternalHostBody, auth: INH_TOKEN_AUTH, roles: ROLES
) -> DraftOut:
    """Add an external host (event managers only)."""
    if not roles.is_event_manager:
        raise HTTPException(status_code=403, detail="Only event managers can add external hosts")
    event = await get_editable_draft(id, roles)
    event.draft.data.hosts.append(Host(id=new_host_id(), type=HostType.EXTERNAL, name=body.name, url=body.url))
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.patch("/{id}/hosts/external/{host_id}")
async def patch_external_host(
    id: PydanticObjectId, host_id: str, body: PatchExternalHostBody, auth: INH_TOKEN_AUTH, roles: ROLES
) -> DraftOut:
    """Patch an external host."""
    event = await get_editable_draft(id, roles)
    host = _find_host(event.draft.data.hosts, host_id)
    if host is None or host.type != HostType.EXTERNAL:
        raise HTTPException(status_code=404, detail="External host not found")
    if "name" in body.model_fields_set:
        host.name = body.name
    if "url" in body.model_fields_set:
        host.url = body.url
    if not (host.name or "").strip():
        raise HTTPException(status_code=400, detail="External host name is required")
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.post("/{id}/hosts/clubs")
async def add_club_host(id: PydanticObjectId, body: AddClubHostBody, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Add one of the caller's clubs as a host."""
    if body.club_id not in owned_club_ids(roles):
        raise HTTPException(status_code=400, detail="You are not a leader of the specified club")
    event = await get_editable_draft(id, roles)
    if any(h.type == HostType.CLUB and h.club_id == body.club_id for h in event.draft.data.hosts):
        raise HTTPException(status_code=400, detail="Club is already a host")
    if body.club_id in event.invitations:
        event.invitations = [club_id for club_id in event.invitations if club_id != body.club_id]
    event.draft.data.hosts.append(Host(id=new_host_id(), type=HostType.CLUB, club_id=body.club_id))
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.post("/{id}/hosts/invitations")
async def invite_club(id: PydanticObjectId, body: InviteClubBody, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Invite another club as a host (pending until accept)."""
    event = await get_editable_draft(id, roles)
    if any(h.type == HostType.CLUB and h.club_id == body.club_id for h in event.draft.data.hosts):
        raise HTTPException(status_code=400, detail="Club is already a host")
    if body.club_id in event.invitations:
        raise HTTPException(status_code=400, detail="Club is already invited")
    event.invitations.append(body.club_id)
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.delete("/{id}/hosts/invitations/{club_id}")
async def delete_invitation(id: PydanticObjectId, club_id: str, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Remove a pending club invitation."""
    event = await get_editable_draft(id, roles)
    if club_id not in event.invitations:
        raise HTTPException(status_code=404, detail="Invitation not found")
    event.invitations = [item for item in event.invitations if item != club_id]
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.delete("/{id}/hosts/{host_id}")
async def delete_host(id: PydanticObjectId, host_id: str, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Remove a host from the draft."""
    event = await get_editable_draft(id, roles)
    before = len(event.draft.data.hosts)
    event.draft.data.hosts = [host for host in event.draft.data.hosts if host.id != host_id]
    if len(event.draft.data.hosts) == before:
        raise HTTPException(status_code=404, detail="Host not found")
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.put("/{id}/hosts/order")
async def order_hosts(id: PydanticObjectId, body: OrderHostsBody, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Reorder hosts; body must list every current host id exactly once."""
    event = await get_editable_draft(id, roles)
    current_ids = [host.id for host in event.draft.data.hosts]
    if sorted(body.host_ids) != sorted(current_ids) or len(body.host_ids) != len(set(body.host_ids)):
        raise HTTPException(status_code=400, detail="host_ids must be a permutation of current host ids")
    by_id = {host.id: host for host in event.draft.data.hosts}
    event.draft.data.hosts = [by_id[host_id] for host_id in body.host_ids]
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


def _find_link(links: list[EventLink], link_id: str) -> EventLink | None:
    for link in links:
        if link.id == link_id:
            return link
    return None


@router.post("/{id}/links")
async def add_link(id: PydanticObjectId, body: AddLinkBody, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Add a related link to the draft."""
    if not (body.url or "").strip():
        raise HTTPException(status_code=400, detail="Link url is required")
    event = await get_editable_draft(id, roles)
    event.draft.data.links.append(EventLink(id=new_link_id(), url=body.url.strip(), name=body.name))
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.patch("/{id}/links/{link_id}")
async def patch_link(
    id: PydanticObjectId, link_id: str, body: PatchLinkBody, auth: INH_TOKEN_AUTH, roles: ROLES
) -> DraftOut:
    """Patch a related link."""
    event = await get_editable_draft(id, roles)
    link = _find_link(event.draft.data.links, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")
    if "url" in body.model_fields_set:
        if body.url is None or not body.url.strip():
            raise HTTPException(status_code=400, detail="Link url is required")
        link.url = body.url.strip()
    if "name" in body.model_fields_set:
        link.name = body.name
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.delete("/{id}/links/{link_id}")
async def delete_link(id: PydanticObjectId, link_id: str, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Remove a related link from the draft."""
    event = await get_editable_draft(id, roles)
    before = len(event.draft.data.links)
    event.draft.data.links = [link for link in event.draft.data.links if link.id != link_id]
    if len(event.draft.data.links) == before:
        raise HTTPException(status_code=404, detail="Link not found")
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.post("/{id}/accept")
async def accept_invitation(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Accept a pending host invitation for one of the caller's clubs."""
    event = await get_viewable_draft(id, roles)
    owned = owned_club_ids(roles)
    invited = owned & set(event.invitations)
    if not invited:
        raise HTTPException(status_code=400, detail="No pending invitation for your clubs")
    club_id = next(iter(invited))
    event.invitations = [item for item in event.invitations if item != club_id]
    if not any(h.type == HostType.CLUB and h.club_id == club_id for h in event.draft.data.hosts):
        event.draft.data.hosts.append(Host(id=new_host_id(), type=HostType.CLUB, club_id=club_id))
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.post("/{id}/decline")
async def decline_invitation(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Decline a pending host invitation for one of the caller's clubs."""
    event = await get_viewable_draft(id, roles)
    owned = owned_club_ids(roles)
    invited = owned & set(event.invitations)
    if not invited:
        raise HTTPException(status_code=400, detail="No pending invitation for your clubs")
    club_id = next(iter(invited))
    event.invitations = [item for item in event.invitations if item != club_id]
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event, roles)


@router.post("/{id}/image")
async def upload_image(
    id: PydanticObjectId, image_file: UploadFile, auth: INH_TOKEN_AUTH, roles: ROLES
) -> ImageUploadResponse:
    """Upload an image for the draft; stores its id in draft.data.image_id."""
    event = await get_editable_draft(id, roles)

    bytes_ = await image_file.read()
    content_type = image_file.content_type
    if content_type is None:  # pragma: no cover
        kind = filetype.guess(bytes_)
        content_type = kind.mime if kind else None

    if content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail=f"Invalid content type ({content_type})")

    image = Image.open(BytesIO(bytes_))
    buf = BytesIO()
    image.save(buf, format="WEBP", quality=90)
    image_bytes = buf.getvalue()

    image_id = str(PydanticObjectId())
    images_repo.put(image_id, image_bytes, "image/webp")

    event.draft.data.image_id = image_id
    event.draft.revision = utcnow()
    await event.save()
    return ImageUploadResponse(image_id=image_id)


@router.get("/{id}/image")
async def get_draft_image(id: PydanticObjectId) -> RedirectResponse:
    """Redirect to the draft image in MinIO (public; for <img src>)."""
    event = await events_repo.get(id)
    if event is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    image_id = event.draft.data.image_id
    if not image_id:
        raise HTTPException(status_code=404, detail="No image available")
    return RedirectResponse(url=images_repo.get_url(image_id))


@router.post("/{id}/restore")
async def restore_draft(id: PydanticObjectId, body: RestoreBody, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Copy the revision and data from submission or public back into the draft."""
    event = await get_editable_draft(id, roles)
    source = event.submission if body.source == "submission" else event.public
    if source is None:
        raise HTTPException(status_code=400, detail=f"No {body.source} to restore from")
    event.draft.data = EventData(**source.data.model_dump())
    event.draft.revision = source.revision
    await event.save()
    return build_draft_out(event, roles)


@router.delete("/{id}")
async def delete_draft(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> None:
    """Delete the draft; allowed only when the event is not published and no submission is pending."""
    event = await get_editable_draft(id, roles)
    if event.creator_id != auth.innohassle_id:
        raise HTTPException(status_code=403, detail="Only the creator can delete the draft")
    if event.public is not None:
        raise HTTPException(status_code=400, detail="Cannot delete a draft while the event is published")
    if event.submission is not None and event.submission.moderation.status == ModerationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Cannot delete a draft while a submission is pending")
    await event.delete()
