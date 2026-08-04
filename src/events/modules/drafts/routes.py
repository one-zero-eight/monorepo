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
from src.events.mongo import EventData, Locale, ModerationStatus
from src.events.schemas import (
    CreateDraft,
    DraftListItem,
    DraftOut,
    Eligibility,
    ImageUploadResponse,
    PatchDraft,
    PatchLocale,
    RestoreBody,
)
from src.events.service import assert_host_allowed, eligibility_reasons, get_own_draft, utcnow
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


@router.post("/")
async def create_draft(body: CreateDraft, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Create a draft event."""
    if not roles.is_club_leader and not roles.is_event_manager:
        raise HTTPException(status_code=403, detail="Only club leaders or event managers can create drafts")
    await assert_host_allowed(body.host, roles)
    _validate_locale_codes(body.locales or [])
    data = EventData(
        starts_at=body.starts_at,
        location=body.location,
        locales={code: Locale() for code in body.locales or []},
        host=body.host,
    )
    event = await events_repo.create(auth.innohassle_id, data)
    return build_draft_out(event)


@router.get("/")
async def list_drafts(auth: INH_TOKEN_AUTH) -> list[DraftListItem]:
    """List the current user's drafts."""
    events = await events_repo.list_by_creator(auth.innohassle_id)
    return [build_draft_list_item(event) for event in events]


@router.get("/{id}")
async def get_draft(id: PydanticObjectId, auth: INH_TOKEN_AUTH) -> DraftOut:
    """Get the current user's draft."""
    event = await get_own_draft(id, auth.innohassle_id)
    return build_draft_out(event)


@router.patch("/{id}")
async def patch_draft(id: PydanticObjectId, body: PatchDraft, auth: INH_TOKEN_AUTH, roles: ROLES) -> DraftOut:
    """Change draft data (starts_at / location / host)."""
    event = await get_own_draft(id, auth.innohassle_id)
    if "host" in body.model_fields_set and body.host is not None:
        await assert_host_allowed(body.host, roles)
    if "starts_at" in body.model_fields_set:
        event.draft.data.starts_at = body.starts_at
    if "location" in body.model_fields_set:
        event.draft.data.location = body.location
    if "host" in body.model_fields_set:
        event.draft.data.host = body.host
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event)


@router.patch("/{id}/locales/{locale}")
async def patch_locale(id: PydanticObjectId, locale: str, body: PatchLocale, auth: INH_TOKEN_AUTH) -> DraftOut:
    """Patch name or description in a locale; auto-creates the locale if missing."""
    event = await get_own_draft(id, auth.innohassle_id)
    _validate_locale_codes([locale])
    current = event.draft.data.locales.get(locale)
    if current is None:
        current = Locale()
        event.draft.data.locales[locale] = current
    if "name" in body.model_fields_set:
        current.name = body.name
    if "description" in body.model_fields_set:
        current.description = body.description
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event)


@router.delete("/{id}/locales/{locale}")
async def delete_locale(id: PydanticObjectId, locale: str, auth: INH_TOKEN_AUTH) -> DraftOut:
    """Delete a locale from the draft."""
    event = await get_own_draft(id, auth.innohassle_id)
    _validate_locale_codes([locale])
    event.draft.data.locales.pop(locale, None)
    event.draft.revision = utcnow()
    await event.save()
    return build_draft_out(event)


@router.post("/{id}/image")
async def upload_image(id: PydanticObjectId, image_file: UploadFile, auth: INH_TOKEN_AUTH) -> ImageUploadResponse:
    """Upload an image for the draft; stores its id in draft.data.image_id."""
    event = await get_own_draft(id, auth.innohassle_id)

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
async def get_draft_image(id: PydanticObjectId, auth: INH_TOKEN_AUTH) -> RedirectResponse:
    """Redirect to the draft image in MinIO."""
    event = await get_own_draft(id, auth.innohassle_id)
    image_id = event.draft.data.image_id
    if not image_id:
        raise HTTPException(status_code=404, detail="No image available")
    return RedirectResponse(url=images_repo.get_url(image_id))


@router.get("/{id}/eligible")
async def check_eligible(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> Eligibility:
    """Check submission guardrails and report which of them are violated."""
    event = await get_own_draft(id, auth.innohassle_id)
    reasons = eligibility_reasons(event, roles)
    return Eligibility(eligible=not reasons, why=reasons)


@router.post("/{id}/restore")
async def restore_draft(id: PydanticObjectId, body: RestoreBody, auth: INH_TOKEN_AUTH) -> DraftOut:
    """Copy the revision and data from submission or public back into the draft."""
    event = await get_own_draft(id, auth.innohassle_id)
    source = event.submission if body.source == "submission" else event.public
    if source is None:
        raise HTTPException(status_code=400, detail=f"No {body.source} to restore from")
    event.draft.data = EventData(**source.data.model_dump())
    event.draft.revision = source.revision
    await event.save()
    return build_draft_out(event)


@router.delete("/{id}")
async def delete_draft(id: PydanticObjectId, auth: INH_TOKEN_AUTH) -> None:
    """Delete the draft; allowed only when the event is not published and no submission is pending."""
    event = await get_own_draft(id, auth.innohassle_id)
    if event.public is not None:
        raise HTTPException(status_code=400, detail="Cannot delete a draft while the event is published")
    if event.submission is not None and event.submission.moderation.status == ModerationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Cannot delete a draft while a submission is pending")
    await event.delete()
