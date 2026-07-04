from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from src.schedule.dependencies import CURRENT_USER_ID_DEPENDENCY
from src.schedule.exceptions import EventGroupNotFoundException, IncorrectCredentialsException, ObjectNotFound
from src.schedule.modules.event_groups.repository import event_group_repository
from src.schedule.modules.predefined.repository import predefined_repository
from src.schedule.modules.users.linked import LinkedCalendarCreate, LinkedCalendarUpdate, LinkedCalendarView
from src.schedule.modules.users.repository import user_repository
from src.schedule.modules.users.schemas import TargetForExport, ViewUser, ViewUserScheduleKey

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={
        **IncorrectCredentialsException.responses,
    },
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/me", responses={200: {"description": "Current user info"}})
async def get_me(user_id: CURRENT_USER_ID_DEPENDENCY) -> ViewUser:
    """
    Get current user info if authenticated
    """

    user = await user_repository.read(user_id)
    return user


class UserPredefinedGroupsResponse(BaseModel):
    event_groups: list[int]


@router.get("/me/predefined", responses={200: {"description": "Predefined event groups for user"}})
async def get_predefined(user_id: CURRENT_USER_ID_DEPENDENCY) -> UserPredefinedGroupsResponse:
    """
    Get predefined event groups for user
    """

    groups = await predefined_repository.get_user_predefined(user_id)
    return UserPredefinedGroupsResponse(event_groups=groups)


@router.post(
    "/me/favorites",
    responses={200: {"description": "Favorite added successfully"}, **EventGroupNotFoundException.responses},
)
async def add_favorite(user_id: CURRENT_USER_ID_DEPENDENCY, group_id: int) -> ViewUser:
    """
    Add favorite to current user
    """
    updated_user = await user_repository.add_favorite(user_id, group_id)
    return updated_user


@router.delete(
    "/me/favorites",
    responses={200: {"description": "Favorite deleted"}},
)
async def delete_favorite(user_id: CURRENT_USER_ID_DEPENDENCY, group_id: int) -> ViewUser:
    """
    Delete favorite from current user
    """

    updated_user = await user_repository.remove_favorite(user_id, group_id)
    return updated_user


@router.post(
    "/me/favorites/hide",
    responses={
        200: {"description": "Favorite hidden"},
        **ObjectNotFound.responses,
    },
)
async def hide_favorite(user_id: CURRENT_USER_ID_DEPENDENCY, group_id: int, hide: bool = True) -> ViewUser:
    """
    Hide favorite from current user
    """
    # check if a group exists

    if await event_group_repository.read(group_id) is None:
        raise ObjectNotFound(f"Event group with id {group_id} does not exist")

    updated_user = await user_repository.set_hidden_event_group(user_id=user_id, group_id=group_id, hide=hide)
    return updated_user


@router.post(
    "/me/linked/hide",
    responses={
        200: {"description": "Linked calendar hidden"},
        **ObjectNotFound.responses,
    },
)
async def hide_linked_calendar(user_id: CURRENT_USER_ID_DEPENDENCY, alias: str, hide: bool = True) -> ViewUser:
    """
    Hide linked calendar from current user
    """
    user = await user_repository.read(user_id)
    if user is None or alias not in user.linked_calendars:
        raise ObjectNotFound(f"Linked calendar with alias {alias} does not exist")

    updated_user = await user_repository.set_linked_calendar_hidden(user_id=user_id, alias=alias, hide=hide)
    return updated_user


@router.post("/me/{target}/hide", responses={200: {"description": "Target hidden"}})
async def hide_target(user_id: CURRENT_USER_ID_DEPENDENCY, target: TargetForExport, hide: bool = True) -> ViewUser:
    """
    Hide music room, sports or moodle from current user
    """

    updated_user = await user_repository.set_hidden(user_id=user_id, target=target, hide=hide)
    return updated_user


@router.post(
    "/me/linked",
    responses={
        200: {"description": "Linked calendar added successfully"},
        409: {"description": "Calendar with this alias already exists"},
    },
)
async def link_calendar(
    linked_calendar: LinkedCalendarCreate, user_id: CURRENT_USER_ID_DEPENDENCY
) -> LinkedCalendarView:
    """
    Add linked calendar to current user
    """
    try:
        calendar = await user_repository.link_calendar(user_id, linked_calendar)
        return calendar
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Calendar with this alias already exists")


@router.delete(
    "/me/linked",
    responses={
        200: {"description": "Linked calendar deleted"},
        **ObjectNotFound.responses,
    },
)
async def delete_linked_calendar(user_id: CURRENT_USER_ID_DEPENDENCY, alias: str) -> ViewUser:
    """
    Delete linked calendar from current user
    """
    user = await user_repository.read(user_id)
    if user is None or alias not in user.linked_calendars:
        raise ObjectNotFound(f"Linked calendar with alias {alias} does not exist")

    updated_user = await user_repository.delete_linked_calendar(user_id=user_id, alias=alias)
    return updated_user


@router.patch(
    "/me/linked",
    responses={
        200: {"description": "Linked calendar updated"},
        409: {"description": "Calendar with this alias already exists"},
        **ObjectNotFound.responses,
    },
)
async def update_linked_calendar(
    user_id: CURRENT_USER_ID_DEPENDENCY, alias: str, linked_calendar: LinkedCalendarUpdate
) -> LinkedCalendarView:
    """
    Update linked calendar for current user
    """
    user = await user_repository.read(user_id)
    if user is None or alias not in user.linked_calendars:
        raise ObjectNotFound(f"Linked calendar with alias {alias} does not exist")

    try:
        updated_calendar = await user_repository.update_linked_calendar(user_id, alias, linked_calendar)
        if updated_calendar is None:
            raise ObjectNotFound(f"Linked calendar with alias {alias} does not exist")
        return updated_calendar
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Calendar with this alias already exists")


class _GetScheduleAccessKeyResponse(BaseModel):
    new: bool
    access_key: ViewUserScheduleKey


@router.post(
    "/me/get-schedule-access-key",
    responses={200: {"description": "Schedule access key for given resource"}},
)
async def generate_user_schedule_key(
    resource_path: str, user_id: CURRENT_USER_ID_DEPENDENCY
) -> _GetScheduleAccessKeyResponse:
    """
    Generate an access key for the user schedule
    """

    key = await user_repository.get_user_schedule_key_for_resource(user_id, resource_path)
    new = False
    if key is None:
        key = await user_repository.generate_user_schedule_key(user_id, resource_path)
        new = True
    return _GetScheduleAccessKeyResponse(new=new, access_key=key)


@router.get(
    "/me/schedule-access-keys",
    responses={200: {"description": "Schedule access keys for user"}},
)
async def get_user_schedule_keys(user_id: CURRENT_USER_ID_DEPENDENCY) -> list[ViewUserScheduleKey]:
    """
    Get all access keys for the user schedule
    """

    keys = await user_repository.get_user_schedule_keys(user_id)
    return keys


@router.delete(
    "/me/schedule-access-key",
    responses={
        200: {"description": "Schedule access key deleted"},
    },
)
async def delete_user_schedule_key(access_key: str, resource_path: str, user_id: CURRENT_USER_ID_DEPENDENCY) -> None:
    """
    Delete an access key for the user schedule
    """

    await user_repository.delete_user_schedule_key(user_id, access_key, resource_path)
    return


@router.post("/me/set-moodle", responses={200: {"description": "Moodle stuff is configured successfully"}})
async def set_user_moodle_data(
    moodle_userid: int, moodle_calendar_authtoken: str, user_id: CURRENT_USER_ID_DEPENDENCY
) -> None:
    await user_repository.set_user_moodle_data(user_id, moodle_userid, moodle_calendar_authtoken)
