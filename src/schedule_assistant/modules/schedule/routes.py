from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response as FastAPIResponse

from src.schedule_assistant.dependencies import VerifyTokenDep
from src.schedule_assistant.modules.schedule import service
from src.schedule_assistant.modules.schedule_config.schemas import CoursesConfig, StudentsGroups

router = APIRouter(prefix="/schedule", tags=["Schedule"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


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


@router.get("/export.xlsx")
async def export_schedule_xlsx(_user_and_token: VerifyTokenDep) -> FastAPIResponse:
    file_bytes, filename = service.export_schedule_xlsx()
    ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "schedule.xlsx"
    quoted = quote(filename)
    return FastAPIResponse(
        content=file_bytes,
        media_type=XLSX_MEDIA_TYPE,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quoted}",
        },
    )
