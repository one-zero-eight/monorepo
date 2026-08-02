import yaml
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ValidationError

from src.schedule_assistant.core_courses.config import CoreCoursesConfig
from src.schedule_assistant.core_courses.location_parser import Item, parse_location_string
from src.schedule_assistant.dependencies import VerifyTokenDep
from src.schedule_assistant.electives.config import ElectivesParserConfig
from src.schedule_assistant.modules.parser.core_courses_adapter import (
    get_grouped_core_courses_lessons,
    grouped_core_course_to_json,
)
from src.schedule_assistant.modules.parser.electives_adapter import (
    get_grouped_elective_lessons,
    grouped_elective_to_json,
)

router = APIRouter(prefix="/parser", tags=["Parser"])


def _omit_none_values(value):
    if isinstance(value, dict):
        return {key: _omit_none_values(nested) for key, nested in value.items() if nested is not None}
    if isinstance(value, list):
        return [_omit_none_values(item) for item in value]
    return value


class ParseLocationStringResponse(BaseModel):
    location_item: Item
    description: str


@router.post("/parse-location-string")
async def parse_location_string_route(
    _user_and_token: VerifyTokenDep, location_string: str
) -> ParseLocationStringResponse:
    location_item = parse_location_string(location_string)
    if location_item is None:
        raise HTTPException(status_code=400, detail="Invalid location string")
    return ParseLocationStringResponse(
        location_item=location_item,
        description=location_item.describe_calendar_behavior(),
    )


@router.post("/parse-core-courses")
async def parse_core_courses_route(
    _user_and_token: VerifyTokenDep, config_yaml: str = Body(media_type="text/yaml")
) -> Response:
    try:
        payload = yaml.safe_load(config_yaml) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail="Invalid request body format") from e

    try:
        parser_config = CoreCoursesConfig.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e

    grouped = await get_grouped_core_courses_lessons(parser_config)
    payload = [_omit_none_values(grouped_core_course_to_json(course)) for course in grouped]

    content = yaml.dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return Response(
        content=content,
        media_type="text/yaml",
        headers={"Content-Disposition": 'attachment; filename="core-courses-lessons.yaml"'},
    )


@router.post("/parse-electives")
async def parse_electives_route(
    _user_and_token: VerifyTokenDep, config_yaml: str = Body(media_type="text/yaml")
) -> Response:
    try:
        payload = yaml.safe_load(config_yaml) or {}
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail="Invalid request body format") from e

    try:
        parser_config = ElectivesParserConfig.model_validate(payload)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors()) from e

    electives = await get_grouped_elective_lessons(parser_config)
    payload = [_omit_none_values(grouped_elective_to_json(elective)) for elective in electives]

    content = yaml.dump(
        payload,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
    )
    return Response(
        content=content,
        media_type="text/yaml",
        headers={"Content-Disposition": 'attachment; filename="electives-lessons.yaml"'},
    )
