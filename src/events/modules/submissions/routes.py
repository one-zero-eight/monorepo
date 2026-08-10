from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from starlette.responses import RedirectResponse

from src.dependencies import INH_TOKEN_AUTH
from src.events import repo as events_repo
from src.events.dependencies import MODERATOR_AUTH, ROLES
from src.events.images_repo import images_repo
from src.events.mongo import Event, Moderation, ModerationStatus, PublicEvent, Submission
from src.events.schemas import DeclineBody, FeedbackBody, SubmissionListItem, SubmissionOut
from src.events.service import build_submission_data, eligibility_reasons, get_editable_draft, utcnow
from src.events.views import build_submission_list_item, build_submission_out

router = APIRouter(
    prefix="/submissions",
    tags=["Submissions"],
    route_class=AutoDeriveResponsesAPIRoute,
)


async def _get_submission_or_404(id: PydanticObjectId) -> tuple[Event, Submission]:
    event = await events_repo.get(id)
    if event is None or event.submission is None:
        raise HTTPException(status_code=404, detail="Submission not found")
    return event, event.submission


@router.post("/{id}")
async def submit_draft(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> SubmissionOut:
    """Submit the draft to moderators."""
    event = await get_editable_draft(id, roles)
    reasons = eligibility_reasons(event, roles)
    if reasons:
        raise HTTPException(status_code=400, detail="; ".join(reasons))
    if event.submission is not None and event.draft.revision == event.submission.revision:
        raise HTTPException(status_code=400, detail="Draft has not changed since the last submission")
    now = utcnow()
    submission = Submission(
        revision=event.draft.revision,
        submitted_at=now,
        moderation=Moderation(status=ModerationStatus.PENDING, feedback=None, updated_at=now),
        data=build_submission_data(event.draft.data),
    )
    event.submission = submission
    await event.save()
    return build_submission_out(event, submission)


@router.get("/")
async def list_submissions(
    auth: INH_TOKEN_AUTH,
    roles: ROLES,
    status: ModerationStatus | None = None,
) -> list[SubmissionListItem]:
    """List submissions; moderators see all, others see only their own."""
    if roles.is_moderator:
        events = await events_repo.list_with_submission()
    else:
        events = await events_repo.list_with_submission_by_creator(auth.innohassle_id)
    items: list[SubmissionListItem] = []
    for event in events:
        if event.submission is None:
            continue
        if status is not None and event.submission.moderation.status != status:
            continue
        items.append(build_submission_list_item(event, event.submission))
    return items


@router.get("/{id}")
async def get_submission(id: PydanticObjectId, auth: INH_TOKEN_AUTH, roles: ROLES) -> SubmissionOut:
    """Get a submission; visible to its author and to moderators."""
    event, submission = await _get_submission_or_404(id)
    if not roles.is_moderator and event.creator_id != auth.innohassle_id:
        raise HTTPException(status_code=404, detail="Submission not found")
    return build_submission_out(event, submission)


@router.get("/{id}/image")
async def get_submission_image(id: PydanticObjectId) -> RedirectResponse:
    """Redirect to the submission image in MinIO (public; for <img src>)."""
    _event, submission = await _get_submission_or_404(id)
    image_id = submission.data.image_id
    if not image_id:
        raise HTTPException(status_code=404, detail="No image available")
    return RedirectResponse(url=images_repo.get_url(image_id))


@router.post("/{id}/approve")
async def approve_submission(id: PydanticObjectId, body: FeedbackBody, moderator: MODERATOR_AUTH) -> SubmissionOut:
    """Approve a submission and publish its data into the public event."""
    event, submission = await _get_submission_or_404(id)
    now = utcnow()
    submission.moderation.status = ModerationStatus.APPROVED
    submission.moderation.feedback = body.feedback
    submission.moderation.updated_at = now
    previous_enrolled = list(event.public.enrolled_emails) if event.public is not None else []
    event.public = PublicEvent(
        revision=submission.revision,
        submitted_at=submission.submitted_at,
        approved_by=moderator.email,
        approved_at=now,
        enrolled_emails=previous_enrolled,
        data=submission.data,
    )
    await event.save()
    return build_submission_out(event, submission)


@router.post("/{id}/decline")
async def decline_submission(id: PydanticObjectId, body: DeclineBody, _: MODERATOR_AUTH) -> SubmissionOut:
    """Decline a submission with required feedback."""
    event, submission = await _get_submission_or_404(id)
    now = utcnow()
    submission.moderation.status = ModerationStatus.DECLINED
    submission.moderation.feedback = body.feedback
    submission.moderation.updated_at = now
    await event.save()
    return build_submission_out(event, submission)


@router.delete("/{id}")
async def delete_submission(id: PydanticObjectId, auth: INH_TOKEN_AUTH) -> None:
    """Delete a pending submission (author only)."""
    event, submission = await _get_submission_or_404(id)
    if event.creator_id != auth.innohassle_id:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.moderation.status != ModerationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Only pending submissions can be deleted")
    event.submission = None
    await event.save()
