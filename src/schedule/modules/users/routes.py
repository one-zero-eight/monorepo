from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from src.inh_accounts_sdk import inh_accounts
from src.schedule.dependencies import CurrentUserIdDep, EventGroupRepoDep, UserRepoDep, VerifyUsersScopeDep
from src.schedule.exceptions import (
    EventGroupNotFoundException,
    ForbiddenException,
    IncorrectCredentialsException,
    ObjectNotFound,
)
from src.schedule.modules.predefined.repository import predefined_repository
from src.schedule.modules.users.linked import LinkedCalendarCreate, LinkedCalendarUpdate, LinkedCalendarView
from src.schedule.modules.users.schemas import AcademicGroupView, TargetForExport, ViewUser, ViewUserScheduleKey

router = APIRouter(
    prefix="/users",
    tags=["Users"],
    responses={
        **IncorrectCredentialsException.responses,
    },
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/me", responses={200: {"description": "Current user info"}})
async def get_me(user_id: CurrentUserIdDep, users: UserRepoDep) -> ViewUser:
    """
    Get current user info if authenticated
    """

    user = await users.read(user_id)
    if user is None:
        raise ObjectNotFound()
    return user


class UserPredefinedGroupsResponse(BaseModel):
    event_groups: list[str]


@router.get("/me/predefined", responses={200: {"description": "Predefined event groups for user"}})
async def get_predefined(user_id: CurrentUserIdDep, users: UserRepoDep) -> UserPredefinedGroupsResponse:
    """
    Get predefined event groups for user
    """
    user = await users.read(user_id)
    if user is None:
        raise ObjectNotFound()
    groups = await predefined_repository.get_user_predefined(user.email)
    return UserPredefinedGroupsResponse(event_groups=groups)


@router.get("/me/academic-groups", responses={200: {"description": "Academic groups of current user"}})
async def get_my_academic_groups(user_id: CurrentUserIdDep, users: UserRepoDep) -> list[AcademicGroupView]:
    """
    Get academic groups of current user, e.g. `B24-DS-01`
    """
    user = await users.read(user_id)
    if user is None:
        raise ObjectNotFound()
    return predefined_repository.get_user_academic_groups(user.email)


@router.get(
    "/by-id/{innohassle_id}/academic-groups",
    responses={
        200: {"description": "Academic groups of the user"},
        **ForbiddenException.responses,
        **ObjectNotFound.responses,
    },
)
async def get_academic_groups_by_innohassle_id(innohassle_id: str, _: VerifyUsersScopeDep) -> list[AcademicGroupView]:
    """
    Get academic groups of the user by InNoHassle Accounts ID.

    Requires token with scope `users` (any user) or `users:<innohassle_id>` (only this user).
    """
    accounts_user = await inh_accounts.get_user(innohassle_id=innohassle_id)
    if accounts_user is None:
        raise ObjectNotFound()
    return predefined_repository.get_user_academic_groups(accounts_user.innopolis_info.email)


@router.post(
    "/me/favorites",
    responses={200: {"description": "Favorite added successfully"}, **EventGroupNotFoundException.responses},
)
async def add_favorite(
    user_id: CurrentUserIdDep, group_alias: str, users: UserRepoDep, event_groups: EventGroupRepoDep
) -> ViewUser:
    """
    Add favorite to current user
    """
    if await event_groups.read_by_alias(group_alias) is None:
        from src.schedule.config import settings
        from src.schedule.modules.schedule_assistant.client import schedule_assistant_client

        virtual_aliases = (
            {group.alias for group in await schedule_assistant_client.get_event_groups()}
            if settings.schedule_assistant is not None
            else set()
        )
        if group_alias not in virtual_aliases:
            raise EventGroupNotFoundException(detail=f"Event group with alias {group_alias} does not exist")
    updated_user = await users.add_favorite(user_id, group_alias)
    return updated_user


@router.delete(
    "/me/favorites",
    responses={200: {"description": "Favorite deleted"}},
)
async def delete_favorite(user_id: CurrentUserIdDep, group_alias: str, users: UserRepoDep) -> ViewUser:
    """
    Delete favorite from current user
    """

    updated_user = await users.remove_favorite(user_id, group_alias)
    return updated_user


@router.post(
    "/me/favorites/hide",
    responses={
        200: {"description": "Favorite hidden"},
        **ObjectNotFound.responses,
    },
)
async def hide_favorite(user_id: CurrentUserIdDep, group_alias: str, users: UserRepoDep, hide: bool = True) -> ViewUser:
    """
    Hide a favorite or predefined event group from current user
    """
    user = await users.read(user_id)
    if user is None:
        raise ObjectNotFound()

    predefined_aliases = await predefined_repository.get_user_predefined(user.email)
    if group_alias not in user.favorite_event_groups and group_alias not in predefined_aliases:
        raise ObjectNotFound(f"Favorite or predefined event group with alias {group_alias} does not exist")

    updated_user = await users.set_hidden_event_group(
        user_id=user_id,
        group_alias=group_alias,
        hide=hide,
    )
    return updated_user


@router.post(
    "/me/linked/hide",
    responses={
        200: {"description": "Linked calendar hidden"},
        **ObjectNotFound.responses,
    },
)
async def hide_linked_calendar(
    user_id: CurrentUserIdDep, alias: str, users: UserRepoDep, hide: bool = True
) -> ViewUser:
    """
    Hide linked calendar from current user
    """
    user = await users.read(user_id)
    if user is None or alias not in user.linked_calendars:
        raise ObjectNotFound(f"Linked calendar with alias {alias} does not exist")

    updated_user = await users.set_linked_calendar_hidden(user_id=user_id, alias=alias, hide=hide)
    return updated_user


@router.post("/me/{target}/hide", responses={200: {"description": "Target hidden"}})
async def hide_target(
    user_id: CurrentUserIdDep, target: TargetForExport, users: UserRepoDep, hide: bool = True
) -> ViewUser:
    """
    Hide music room, sports or moodle from current user
    """

    updated_user = await users.set_hidden(user_id=user_id, target=target, hide=hide)
    return updated_user


@router.post(
    "/me/linked",
    responses={
        200: {"description": "Linked calendar added successfully"},
        409: {"description": "Calendar with this alias already exists"},
    },
)
async def link_calendar(
    linked_calendar: LinkedCalendarCreate, user_id: CurrentUserIdDep, users: UserRepoDep
) -> LinkedCalendarView:
    """
    Add linked calendar to current user
    """
    try:
        calendar = await users.link_calendar(user_id, linked_calendar)
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
async def delete_linked_calendar(user_id: CurrentUserIdDep, alias: str, users: UserRepoDep) -> ViewUser:
    """
    Delete linked calendar from current user
    """
    user = await users.read(user_id)
    if user is None or alias not in user.linked_calendars:
        raise ObjectNotFound(f"Linked calendar with alias {alias} does not exist")

    updated_user = await users.delete_linked_calendar(user_id=user_id, alias=alias)
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
    user_id: CurrentUserIdDep, alias: str, linked_calendar: LinkedCalendarUpdate, users: UserRepoDep
) -> LinkedCalendarView:
    """
    Update linked calendar for current user
    """
    user = await users.read(user_id)
    if user is None or alias not in user.linked_calendars:
        raise ObjectNotFound(f"Linked calendar with alias {alias} does not exist")

    try:
        updated_calendar = await users.update_linked_calendar(user_id, alias, linked_calendar)
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
    resource_path: str, user_id: CurrentUserIdDep, users: UserRepoDep
) -> _GetScheduleAccessKeyResponse:
    """
    Generate an access key for the user schedule
    """

    if resource_path == f"/users/{user_id}/workshops.ics":
        resource_path = f"/users/{user_id}/events.ics"

    key = await users.get_user_schedule_key_for_resource(user_id, resource_path)
    new = False
    if key is None:
        key = await users.generate_user_schedule_key(user_id, resource_path)
        new = True
    return _GetScheduleAccessKeyResponse(new=new, access_key=key)


@router.get(
    "/me/schedule-access-keys",
    responses={200: {"description": "Schedule access keys for user"}},
)
async def get_user_schedule_keys(user_id: CurrentUserIdDep, users: UserRepoDep) -> list[ViewUserScheduleKey]:
    """
    Get all access keys for the user schedule
    """

    keys = await users.get_user_schedule_keys(user_id)
    return keys


@router.delete(
    "/me/schedule-access-key",
    responses={
        200: {"description": "Schedule access key deleted"},
    },
)
async def delete_user_schedule_key(
    access_key: str, resource_path: str, user_id: CurrentUserIdDep, users: UserRepoDep
) -> None:
    """
    Delete an access key for the user schedule
    """

    await users.delete_user_schedule_key(user_id, access_key, resource_path)
    return


@router.post("/me/set-moodle", responses={200: {"description": "Moodle stuff is configured successfully"}})
async def set_user_moodle_data(
    moodle_userid: int, moodle_calendar_authtoken: str, user_id: CurrentUserIdDep, users: UserRepoDep
) -> None:
    await users.set_user_moodle_data(user_id, moodle_userid, moodle_calendar_authtoken)
