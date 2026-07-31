from fastapi import APIRouter

from src.schedule_assistant.dependencies import VerifyTokenDep, is_moderator_email
from src.schedule_assistant.schema_base import ScheduleAssistantSchema

router = APIRouter(tags=["Users"])


class MeResponse(ScheduleAssistantSchema):
    email: str
    "Innopolis email of the authenticated user"
    is_moderator: bool
    "Whether the user may modify schedule-assistant data"


@router.get("/me")
async def get_me(user_and_token: VerifyTokenDep) -> MeResponse:
    user, _token = user_and_token
    return MeResponse(
        email=user.email,
        is_moderator=is_moderator_email(user.email),
    )
