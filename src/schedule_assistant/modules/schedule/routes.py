from urllib.parse import quote

from fastapi import APIRouter
from fastapi.responses import Response as FastAPIResponse

from src.schedule_assistant.dependencies import ServiceApiKeyDep, VerifyTokenDep
from src.schedule_assistant.modules.schedule import service
from src.schedule_assistant.modules.schedule.schemas import (
    BatchAliasesIcsRequest,
    ListVirtualEventGroupsResponse,
    PredefinedAliasesResponse,
)
from src.schedule_assistant.modules.schedule_config.schemas import CoursesConfig, StudentsGroups

router = APIRouter(prefix="/schedule", tags=["Schedule"])
integration_router = APIRouter(prefix="/integration", tags=["Schedule Integration"])

XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ICS_MEDIA_TYPE = "text/calendar; charset=utf-8"


def _user_email(user_and_token: VerifyTokenDep) -> str:
    user, _token = user_and_token
    return user.email


@router.get("/my-groups")
async def get_my_groups(user_and_token: VerifyTokenDep) -> list[StudentsGroups]:
    return service.get_my_groups(_user_email(user_and_token))


@integration_router.get("/event-groups")
async def list_event_groups(_api_key: ServiceApiKeyDep) -> ListVirtualEventGroupsResponse:
    return ListVirtualEventGroupsResponse(event_groups=service.list_virtual_event_groups())


@integration_router.get("/users/{email}/predefined")
async def get_predefined_aliases(email: str, _api_key: ServiceApiKeyDep) -> PredefinedAliasesResponse:
    return PredefinedAliasesResponse(event_groups=service.get_predefined_aliases(email))


@integration_router.post("/event-groups/schedule.ics")
async def get_event_groups_ics(
    request: BatchAliasesIcsRequest,
    _api_key: ServiceApiKeyDep,
) -> FastAPIResponse:
    return FastAPIResponse(content=service.get_aliases_ics(request.aliases), media_type=ICS_MEDIA_TYPE)


@integration_router.get("/event-groups/{alias}/schedule.ics")
async def get_event_group_ics(alias: str, _api_key: ServiceApiKeyDep) -> FastAPIResponse:
    return FastAPIResponse(content=service.get_group_ics(alias), media_type=ICS_MEDIA_TYPE)


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
