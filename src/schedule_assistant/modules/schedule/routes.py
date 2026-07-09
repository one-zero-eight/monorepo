from fastapi import APIRouter

from src.schedule_assistant.dependencies import VerifyTokenDep
from src.schedule_assistant.modules.schedule import service
from src.schedule_assistant.modules.schedule_config.schemas import CoursesConfig, StudentsGroups

router = APIRouter(prefix="/schedule", tags=["Schedule"])


def _user_email(user_and_token: VerifyTokenDep) -> str:
    user, _token = user_and_token
    return user.email


@router.get("/my-groups")
async def get_my_groups(user_and_token: VerifyTokenDep) -> list[StudentsGroups]:
    return service.get_my_groups(_user_email(user_and_token))


@router.get("/groups/{group_code}")
async def get_group_schedule(group_code: str, _user_and_token: VerifyTokenDep) -> CoursesConfig:
    return service.get_group_schedule(group_code)


@router.get("/instructors/{instructor_id}")
async def get_instructor_schedule(instructor_id: str, _user_and_token: VerifyTokenDep) -> CoursesConfig:
    return service.get_instructor_schedule(instructor_id)
