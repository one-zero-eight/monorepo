from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.schedule.db import EventGroupRepoDep
from src.schedule.dependencies import VerifyParserOrAdminDep
from src.schedule.exceptions import ForbiddenException, IncorrectCredentialsException
from src.schedule.modules.predefined.repository import predefined_repository
from src.schedule.modules.predefined.storage import JsonPredefinedUsers

router = APIRouter(prefix="", tags=["Predefined"], route_class=AutoDeriveResponsesAPIRoute)


@router.get(
    "/get-predefined-data",
    responses={
        200: {"description": "Predefined data"},
        **IncorrectCredentialsException.responses,
        **ForbiddenException.responses,
    },
)
async def get_predefined_data(_: VerifyParserOrAdminDep) -> JsonPredefinedUsers:
    return predefined_repository.storage


@router.post(
    "/update-predefined-data",
    responses={
        200: {
            "description": "Predefined data updated successfully",
        },
        **IncorrectCredentialsException.responses,
        **ForbiddenException.responses,
    },
)
async def update_predefined_data(
    _: VerifyParserOrAdminDep,
    user_storage: JsonPredefinedUsers,
    event_group_repo: EventGroupRepoDep,
) -> list[str]:
    from src.schedule.modules.predefined.utils import setup_predefined_data_from_object

    setup_predefined_data_from_object(user_storage)

    user_groups = set()
    for user in user_storage.users:
        user_groups.update(user.groups)

    event_groups = await event_group_repo.read_all()
    event_group_aliases = {group.alias for group in event_groups}

    non_existent_groups_from_user = user_groups - event_group_aliases

    non_existent_groups_from_academic_groups = {
        group.event_group_alias for group in user_storage.academic_groups if group.event_group_alias
    } - event_group_aliases

    return list(non_existent_groups_from_user) + list(non_existent_groups_from_academic_groups)
