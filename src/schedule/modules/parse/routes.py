__all__ = ["router"]

from itertools import groupby

import aiofiles
import icalendar
from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.schedule.dependencies import VERIFY_PARSER_DEPENDENCY
from src.schedule.exceptions import IncorrectCredentialsException
from src.schedule.modules.event_groups.repository import event_group_repository
from src.schedule.modules.event_groups.schemas import CreateEventGroup
from src.schedule.modules.parse.bootcamp import AcademicGroup, BootcampParser, BootcampParserConfig, BuddyGroup
from src.schedule.modules.parse.cleaning import CleaningParser, CleaningParserConfig
from src.schedule.modules.tags.schemas import CreateTag
from src.schedule.utils import get_base_calendar, locate_ics_by_path, sluggify, validate_calendar

router = APIRouter(prefix="/parse", tags=["Parse"], route_class=AutoDeriveResponsesAPIRoute)


async def save_ics(calendar: icalendar.Calendar, event_group_path: str, event_group_id: int):
    """
    Load .ics file to event group by event group id and save file to predefined path
    """
    validate_calendar(calendar)
    content = calendar.to_ical()
    ics_path = locate_ics_by_path(event_group_path)

    if ics_path.exists():
        async with aiofiles.open(ics_path, "rb") as f:
            old_content = await f.read()
            if old_content == content:
                return  # File already exists and content is the same
    # make directory if not exists
    ics_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(ics_path, "wb") as f:
        await f.write(content)

    await event_group_repository.update_timestamp(event_group_id)


@router.post(
    "/cleaning",
    responses={**IncorrectCredentialsException.responses},
)
async def parse_cleaning_schedule(_: VERIFY_PARSER_DEPENDENCY, config: CleaningParserConfig) -> None:
    cleaning_tag = CreateTag(alias="cleaning", name="Cleaning", type="category")
    cleaning_cleaning_tag = CreateTag(alias="room-cleaning", name="Room Cleaning", type="cleaning")
    linen_change_tag = CreateTag(alias="linen-change", name="Linen Change", type="cleaning")
    parser = CleaningParser(config)

    # ----- Cleaning schedule -----
    cleaning_events = parser.get_cleaning_events()
    cleaning_events = sorted(cleaning_events, key=lambda x: x.location)

    for location, events_iter in groupby(cleaning_events, key=lambda x: x.location):
        events = list(events_iter)
        calendar = get_base_calendar()
        calendar["x-wr-calname"] = f"Cleaning: {location}"

        for event in events:
            vevent = event.get_vevent()
            calendar.add_component(vevent)

        group_alias = f"cleaning-{sluggify(location)}"
        path = f"cleaning/{group_alias}.ics"

        event_group = CreateEventGroup(
            alias=group_alias,
            name=f"Cleaning: {location}",
            description=f"Cleaning schedule for {location}",
            tags=[cleaning_tag, cleaning_cleaning_tag],
            path=path,
        )
        event_group_id = await event_group_repository.create_or_update(event_group)
        await save_ics(calendar, path, event_group_id)

    # --- Linen Change Schedule ---
    linen_change_events = parser.get_linen_change_schedule()
    linen_change_events = sorted(linen_change_events, key=lambda x: x.location)

    for location, events_iter in groupby(linen_change_events, key=lambda x: x.location):
        events = list(events_iter)

        calendar = get_base_calendar()
        calendar["x-wr-calname"] = f"Linen Change: {location}"

        for event in events:
            vevent = event.get_vevent()
            calendar.add_component(vevent)

        group_alias = f"linen-change-{sluggify(location)}"
        path = f"cleaning/{group_alias}.ics"

        event_group = CreateEventGroup(
            alias=group_alias,
            name=f"Linen Change: {location}",
            description=f"Linen change schedule for {location}",
            tags=[cleaning_tag, linen_change_tag],
            path=path,
        )
        event_group_id = await event_group_repository.create_or_update(event_group)
        await save_ics(calendar, path, event_group_id)


@router.post(
    "/bootcamp",
    responses={**IncorrectCredentialsException.responses},
)
async def parse_bootcamp_schedule(_: VERIFY_PARSER_DEPENDENCY, config: BootcampParserConfig) -> None:
    bootcamp_tag = CreateTag(alias="bootcamp2026", name="Bootcamp", type="category")
    academic_tag = CreateTag(alias="academic", name="Academic", type="bootcamp2026")
    buddy_tag = CreateTag(alias="buddy", name="Buddy", type="bootcamp2026")

    parser = BootcampParser(config)

    for group, events in parser.parse():
        calendar = get_base_calendar()

        for event in events:
            vevent = event.get_vevent()
            calendar.add_component(vevent)

        if isinstance(group, AcademicGroup):
            calendar["x-wr-calname"] = f"Bootcamp: {group.name}"
            group_alias = f"bootcamp-academic-{sluggify(group.name)}"
            path = f"bootcamp/{group_alias}.ics"

            event_group = CreateEventGroup(
                alias=group_alias,
                name=f"{group.name}",
                description=f"Bootcamp schedule for {group.name}",
                tags=[bootcamp_tag, academic_tag],
                path=path,
            )
        elif isinstance(group, BuddyGroup):
            calendar["x-wr-calname"] = f"Bootcamp: Buddy group {group.number}"
            group_alias = f"bootcamp-buddy-group-{group.number}"
            path = f"bootcamp/{group_alias}.ics"

            event_group = CreateEventGroup(
                alias=group_alias,
                name=f"{group.number} - {group.name}",
                description=f"Bootcamp schedule for buddy group {group.number}",
                tags=[bootcamp_tag, buddy_tag],
                path=path,
            )
        else:
            raise NotImplementedError

        event_group_id = await event_group_repository.create_or_update(event_group)
        await save_ics(calendar, path, event_group_id)
