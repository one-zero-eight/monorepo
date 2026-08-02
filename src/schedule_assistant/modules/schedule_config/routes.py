from typing import Annotated

import yaml
from fastapi import APIRouter, Body, File, HTTPException, Response, UploadFile, status
from pydantic import ValidationError

from src.schedule_assistant.dependencies import ModeratorDep, VerifyTokenDep, is_moderator_email
from src.schedule_assistant.modules.schedule_config.event_log import ConfigChangeEvent, ConfigChangeEventSummary
from src.schedule_assistant.modules.schedule_config.instructor_meetings import count_meetings_by_instructor
from src.schedule_assistant.modules.schedule_config.repository import schedule_config_repository
from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    InstructorConfig,
    InstructorListItem,
    RoomConfig,
    ScheduleConfig,
    ScheduleConfigUpdate,
    StudentsGroups,
    TermConfig,
    TermPartialUpdate,
)
from src.schedule_assistant.modules.schedule_config.visibility import filter_scheduled_instructors

router = APIRouter(prefix="/schedule-config", tags=["Schedule config"])

YamlBody = Annotated[str, Body(media_type="text/yaml")]


def _schedule_config_to_update(config: ScheduleConfig) -> ScheduleConfigUpdate:
    return ScheduleConfigUpdate(
        term=TermPartialUpdate.model_validate(config.term.model_dump()),
        rooms=config.rooms,
        instructors=config.instructors,
        students_groups=config.students_groups,
        courses=config.courses,
    )


def _normalize_schedule_config_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        return payload
    if "sections" not in payload:
        return payload
    term = dict(payload.get("term") or {})
    if "sections" not in term:
        term["sections"] = payload["sections"]
    normalized = {key: value for key, value in payload.items() if key != "sections"}
    normalized["term"] = term
    return normalized


def _parse_yaml_schedule_config_update(text: str) -> ScheduleConfigUpdate:
    try:
        payload = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YAML",
        ) from exc
    payload = _normalize_schedule_config_payload(payload)
    try:
        return _schedule_config_to_update(ScheduleConfig.model_validate(payload))
    except ValidationError:
        try:
            return ScheduleConfigUpdate.model_validate(payload)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=exc.errors(),
            ) from exc


def _moderator_email(moderator: ModeratorDep) -> str:
    user, _token = moderator
    return user.email


def _set_revision_etag(response: Response, revision: int) -> None:
    response.headers["ETag"] = f'"{revision}"'


def _assembled_for_user(user_and_token: VerifyTokenDep) -> ScheduleConfig:
    config = schedule_config_repository.get_assembled()
    user, _token = user_and_token
    if is_moderator_email(user.email):
        return config
    filtered = filter_scheduled_instructors(InstructorConfig(instructors=config.instructors), config.courses)
    return config.model_copy(update={"instructors": filtered.instructors})


def _history_snapshot_for_user(event_id: str, user_and_token: VerifyTokenDep) -> ScheduleConfig:
    snapshot = schedule_config_repository.get_history_snapshot(event_id)
    user, _token = user_and_token
    if is_moderator_email(user.email):
        return snapshot
    filtered = filter_scheduled_instructors(InstructorConfig(instructors=snapshot.instructors), snapshot.courses)
    return snapshot.model_copy(update={"instructors": filtered.instructors})


@router.get("/")
async def get_schedule_config(response: Response, user_and_token: VerifyTokenDep) -> ScheduleConfig:
    _set_revision_etag(response, schedule_config_repository.get_revision())
    return _assembled_for_user(user_and_token)


@router.put("/")
async def put_schedule_config(
    response: Response,
    moderator: ModeratorDep,
    config: ScheduleConfigUpdate,
) -> ScheduleConfig:
    saved_config, revision = schedule_config_repository.set_config(
        config,
        saved_by=_moderator_email(moderator),
    )
    _set_revision_etag(response, revision)
    return saved_config


@router.put("/yaml")
async def put_schedule_config_yaml(
    response: Response,
    moderator: ModeratorDep,
    yaml_text: YamlBody,
) -> ScheduleConfig:
    config = _parse_yaml_schedule_config_update(yaml_text)
    saved_config, revision = schedule_config_repository.set_config(
        config,
        saved_by=_moderator_email(moderator),
    )
    _set_revision_etag(response, revision)
    return saved_config


@router.put("/yaml-file")
async def put_schedule_config_yaml_file(
    response: Response,
    moderator: ModeratorDep,
    file: Annotated[UploadFile, File(description="Schedule config YAML file")],
) -> ScheduleConfig:
    raw = await file.read()
    try:
        yaml_text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be UTF-8 text",
        ) from exc
    config = _parse_yaml_schedule_config_update(yaml_text)
    saved_config, revision = schedule_config_repository.set_config(
        config,
        saved_by=_moderator_email(moderator),
    )
    _set_revision_etag(response, revision)
    return saved_config


@router.get("/term")
async def get_term(_user_and_token: VerifyTokenDep) -> TermConfig | None:
    return schedule_config_repository.get_term()


@router.put("/term")
async def put_term(response: Response, moderator: ModeratorDep, term: TermConfig) -> TermConfig:
    saved, revision = schedule_config_repository.set_term(
        term,
        saved_by=_moderator_email(moderator),
    )
    _set_revision_etag(response, revision)
    return saved


@router.get("/courses")
async def list_courses(_user_and_token: VerifyTokenDep) -> list[CourseConfig]:
    return schedule_config_repository.list_courses()


@router.post("/courses", status_code=status.HTTP_201_CREATED)
async def create_course(response: Response, moderator: ModeratorDep, course: CourseConfig) -> CourseConfig:
    saved, revision = schedule_config_repository.create_course(course, saved_by=_moderator_email(moderator))
    _set_revision_etag(response, revision)
    return saved


@router.get("/courses/{course_name:path}")
async def get_course(course_name: str, _user_and_token: VerifyTokenDep) -> CourseConfig:
    course = schedule_config_repository.get_course(course_name)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course not found: {course_name!r}")
    return course


@router.put("/courses/{course_name:path}")
async def update_course(
    response: Response,
    moderator: ModeratorDep,
    course_name: str,
    course: CourseConfig,
) -> CourseConfig:
    saved, revision = schedule_config_repository.update_course(
        course_name,
        course,
        saved_by=_moderator_email(moderator),
    )
    _set_revision_etag(response, revision)
    return saved


@router.delete("/courses/{course_name:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(response: Response, moderator: ModeratorDep, course_name: str) -> None:
    revision = schedule_config_repository.delete_course(course_name, saved_by=_moderator_email(moderator))
    _set_revision_etag(response, revision)


@router.get("/instructors")
async def list_instructors(_user_and_token: VerifyTokenDep) -> list[InstructorListItem]:
    instructors = schedule_config_repository.list_instructors()
    term = schedule_config_repository.get_term()
    courses = schedule_config_repository.list_courses()
    counts = count_meetings_by_instructor(
        courses,
        term,
        [instructor.id for instructor in instructors],
    )
    return [
        InstructorListItem(
            **instructor.model_dump(),
            meetings_count=counts.get(instructor.id, 0),
        )
        for instructor in instructors
    ]


@router.post("/instructors", status_code=status.HTTP_201_CREATED)
async def create_instructor(
    response: Response,
    moderator: ModeratorDep,
    instructor: InstructorConfig.Instructor,
) -> InstructorConfig.Instructor:
    saved, revision = schedule_config_repository.create_instructor(
        instructor,
        saved_by=_moderator_email(moderator),
    )
    _set_revision_etag(response, revision)
    return saved


@router.get("/instructors/{instructor_id:path}")
async def get_instructor(instructor_id: str, _user_and_token: VerifyTokenDep) -> InstructorConfig.Instructor:
    instructor = schedule_config_repository.get_instructor(instructor_id)
    if instructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Instructor not found: {instructor_id!r}")
    return instructor


@router.put("/instructors/{instructor_id:path}")
async def update_instructor(
    response: Response,
    moderator: ModeratorDep,
    instructor_id: str,
    instructor: InstructorConfig.Instructor,
) -> InstructorConfig.Instructor:
    saved, revision = schedule_config_repository.update_instructor(
        instructor_id,
        instructor,
        saved_by=_moderator_email(moderator),
    )
    _set_revision_etag(response, revision)
    return saved


@router.delete("/instructors/{instructor_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instructor(response: Response, moderator: ModeratorDep, instructor_id: str) -> None:
    revision = schedule_config_repository.delete_instructor(instructor_id, saved_by=_moderator_email(moderator))
    _set_revision_etag(response, revision)


@router.get("/student-groups")
async def list_student_groups(_user_and_token: VerifyTokenDep) -> list[StudentsGroups]:
    return schedule_config_repository.list_student_groups()


@router.post("/student-groups", status_code=status.HTTP_201_CREATED)
async def create_student_group(response: Response, moderator: ModeratorDep, group: StudentsGroups) -> StudentsGroups:
    saved, revision = schedule_config_repository.create_student_group(group, saved_by=_moderator_email(moderator))
    _set_revision_etag(response, revision)
    return saved


@router.get("/student-groups/{code:path}")
async def get_student_group(code: str, _user_and_token: VerifyTokenDep) -> StudentsGroups:
    group = schedule_config_repository.get_student_group(code)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student group not found: {code!r}")
    return group


@router.put("/student-groups/{code:path}")
async def update_student_group(
    response: Response,
    moderator: ModeratorDep,
    code: str,
    group: StudentsGroups,
) -> StudentsGroups:
    saved, revision = schedule_config_repository.update_student_group(
        code,
        group,
        saved_by=_moderator_email(moderator),
    )
    _set_revision_etag(response, revision)
    return saved


@router.delete("/student-groups/{code:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student_group(response: Response, moderator: ModeratorDep, code: str) -> None:
    revision = schedule_config_repository.delete_student_group(code, saved_by=_moderator_email(moderator))
    _set_revision_etag(response, revision)


@router.get("/rooms")
async def list_rooms(_user_and_token: VerifyTokenDep) -> list[RoomConfig.Room]:
    return schedule_config_repository.list_rooms()


@router.post("/rooms", status_code=status.HTTP_201_CREATED)
async def create_room(response: Response, moderator: ModeratorDep, room: RoomConfig.Room) -> RoomConfig.Room:
    saved, revision = schedule_config_repository.create_room(room, saved_by=_moderator_email(moderator))
    _set_revision_etag(response, revision)
    return saved


@router.get("/rooms/{room_id:path}")
async def get_room(room_id: str, _user_and_token: VerifyTokenDep) -> RoomConfig.Room:
    room = schedule_config_repository.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Room not found: {room_id!r}")
    return room


@router.put("/rooms/{room_id:path}")
async def update_room(
    response: Response,
    moderator: ModeratorDep,
    room_id: str,
    room: RoomConfig.Room,
) -> RoomConfig.Room:
    saved, revision = schedule_config_repository.update_room(room_id, room, saved_by=_moderator_email(moderator))
    _set_revision_etag(response, revision)
    return saved


@router.delete("/rooms/{room_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(response: Response, moderator: ModeratorDep, room_id: str) -> None:
    revision = schedule_config_repository.delete_room(room_id, saved_by=_moderator_email(moderator))
    _set_revision_etag(response, revision)


@router.get("/history/{event_id}/snapshot")
async def get_history_snapshot(event_id: str, user_and_token: VerifyTokenDep) -> ScheduleConfig:
    return _history_snapshot_for_user(event_id, user_and_token)


@router.get("/history/{event_id}")
async def get_history_event(event_id: str, _user_and_token: VerifyTokenDep) -> ConfigChangeEvent:
    return schedule_config_repository.get_history_event(event_id)


@router.get("/history")
async def list_history(_user_and_token: VerifyTokenDep) -> list[ConfigChangeEventSummary]:
    return schedule_config_repository.list_history()
