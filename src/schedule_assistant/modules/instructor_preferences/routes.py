import datetime as dtm

from fastapi import APIRouter, HTTPException, status

from src.schedule_assistant.dependencies import ModeratorDep, VerifyTokenDep
from src.schedule_assistant.modules.instructor_preferences.repository import (
    preference_invite_repository,
)
from src.schedule_assistant.modules.instructor_preferences.schemas import (
    InstructorPreferenceForm,
    InstructorPreferenceUpdate,
    PreferenceShareLinkResponse,
)
from src.schedule_assistant.modules.schedule_config.repository import schedule_config_repository
from src.schedule_assistant.modules.schedule_config.schemas import InstructorConfig, InstructorSlotPreferenceEntry
from src.schedule_assistant.modules.schedule_config.validation import validate_instructors
from src.schedule_assistant.modules.solver.instructor_preferences import validate_instructor_slot_preferences

router = APIRouter(prefix="/instructor-preferences", tags=["Instructor Preferences"])


def _find_instructor_by_email(email: str) -> InstructorConfig.Instructor | None:
    needle = email.strip().casefold()
    if not needle:
        return None
    for instructor in schedule_config_repository.list_instructors():
        if (instructor.email or "").strip().casefold() == needle:
            return instructor
    return None


def _preference_form(instructor: InstructorConfig.Instructor) -> InstructorPreferenceForm:
    term = schedule_config_repository.get_term()
    if term is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term is not configured")
    return InstructorPreferenceForm(
        instructor_id=instructor.id,
        instructor_name=instructor.name_ru or instructor.name_en or instructor.email or instructor.id,
        email=instructor.email,
        term=term,
        slot_preferences=list(instructor.slot_preferences),
    )


def _save_slot_preferences(
    instructor: InstructorConfig.Instructor,
    slot_preferences: list[InstructorSlotPreferenceEntry],
    *,
    saved_by: str,
) -> InstructorConfig.Instructor:
    term = schedule_config_repository.get_term()
    if term is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Term is not configured")

    updated = instructor.model_copy(update={"slot_preferences": slot_preferences})
    preference_errors = validate_instructor_slot_preferences(updated, term)
    if preference_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=preference_errors)

    instructors = InstructorConfig(instructors=[updated])
    validation_errors = validate_instructors(instructors, term=term)
    if validation_errors:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=validation_errors)

    saved, _revision = schedule_config_repository.update_instructor(
        instructor.id,
        updated,
        saved_by=saved_by,
    )
    return saved


def _instructor_for_invite_key(token: str) -> InstructorConfig.Instructor:
    invite = preference_invite_repository.get_active_by_key(token)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired preference link",
        )
    instructor = schedule_config_repository.get_instructor(invite.instructor_id)
    if instructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Instructor not found")
    return instructor


@router.get("/me")
async def get_my_preferences(user_and_token: VerifyTokenDep) -> InstructorPreferenceForm:
    user, _token = user_and_token
    instructor = _find_instructor_by_email(user.email)
    if instructor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No instructor profile matches your email",
        )
    return _preference_form(instructor)


@router.put("/me")
async def update_my_preferences(
    user_and_token: VerifyTokenDep,
    body: InstructorPreferenceUpdate,
) -> InstructorPreferenceForm:
    user, _token = user_and_token
    instructor = _find_instructor_by_email(user.email)
    if instructor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No instructor profile matches your email",
        )
    saved = _save_slot_preferences(
        instructor,
        body.slot_preferences,
        saved_by=user.email,
    )
    return _preference_form(saved)


@router.post("/{instructor_id:path}/share-link")
async def create_preference_share_link(
    instructor_id: str,
    moderator: ModeratorDep,
) -> PreferenceShareLinkResponse:
    instructor = schedule_config_repository.get_instructor(instructor_id)
    if instructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Instructor not found: {instructor_id!r}")

    user, _tok = moderator
    invite = preference_invite_repository.get_or_create_for_instructor(
        instructor.id,
        created_by=user.email,
    )
    expires_at = invite.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=dtm.UTC)
    return PreferenceShareLinkResponse(token=invite.key, expires_at=expires_at)


@router.get("/link/{token}")
async def get_preferences_by_token(token: str) -> InstructorPreferenceForm:
    return _preference_form(_instructor_for_invite_key(token))


@router.put("/link/{token}")
async def update_preferences_by_token(
    token: str,
    body: InstructorPreferenceUpdate,
) -> InstructorPreferenceForm:
    instructor = _instructor_for_invite_key(token)
    saved = _save_slot_preferences(
        instructor,
        body.slot_preferences,
        saved_by=f"preference-link:{instructor.id}",
    )
    return _preference_form(saved)
