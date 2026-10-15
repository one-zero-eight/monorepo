from typing import Annotated

import yaml
from fastapi import APIRouter, Body, File, HTTPException, Query, Response, UploadFile, status
from pydantic import ValidationError

from src.schedule_assistant.dependencies import (
    ModeratorDep,
    ScheduleConfigRepoDep,
    VerifyTokenDep,
    is_moderator_email,
)
from src.schedule_assistant.modules.schedule_config.instructor_meetings import count_meetings_by_instructor
from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    InstructorConfig,
    InstructorMeetingsCountsResponse,
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


def _parse_yaml_schedule_config_update(text: str) -> ScheduleConfigUpdate:
    try:
        payload = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid YAML",
        ) from exc
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


def _set_revision_etag(response: Response, revision: int) -> None:
    response.headers["ETag"] = f'"{revision}"'


def _assembled_for_user(config_repo: ScheduleConfigRepository, user_and_token: VerifyTokenDep) -> ScheduleConfig:
    config = config_repo.get_assembled()
    user, _token = user_and_token
    if is_moderator_email(user.email):
        return config
    filtered = filter_scheduled_instructors(InstructorConfig(instructors=config.instructors), config.courses)
    return config.model_copy(update={"instructors": filtered.instructors})


@router.get("/")
async def get_schedule_config(
    config_repo: ScheduleConfigRepoDep, response: Response, user_and_token: VerifyTokenDep
) -> ScheduleConfig:
    _set_revision_etag(response, config_repo.get_revision())
    return _assembled_for_user(config_repo, user_and_token)


@router.put("/")
async def put_schedule_config(
    config_repo: ScheduleConfigRepoDep,
    response: Response,
    moderator: ModeratorDep,
    config: ScheduleConfigUpdate,
) -> ScheduleConfig:
    saved_config, revision = config_repo.set_config(config)
    _set_revision_etag(response, revision)
    return saved_config


@router.put("/yaml")
async def put_schedule_config_yaml(
    config_repo: ScheduleConfigRepoDep,
    response: Response,
    moderator: ModeratorDep,
    yaml_text: YamlBody,
) -> ScheduleConfig:
    config = _parse_yaml_schedule_config_update(yaml_text)
    saved_config, revision = config_repo.set_config(config)
    _set_revision_etag(response, revision)
    return saved_config


@router.put("/yaml-file")
async def put_schedule_config_yaml_file(
    config_repo: ScheduleConfigRepoDep,
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
    saved_config, revision = config_repo.set_config(config)
    _set_revision_etag(response, revision)
    return saved_config


@router.get("/term")
async def get_term(config_repo: ScheduleConfigRepoDep, _user_and_token: VerifyTokenDep) -> TermConfig | None:
    return config_repo.get_term()


@router.put("/term")
async def put_term(
    config_repo: ScheduleConfigRepoDep, response: Response, moderator: ModeratorDep, term: TermConfig
) -> TermConfig:
    saved, revision = config_repo.set_term(term)
    _set_revision_etag(response, revision)
    return saved


@router.get("/courses")
async def list_courses(config_repo: ScheduleConfigRepoDep, _user_and_token: VerifyTokenDep) -> list[CourseConfig]:
    return config_repo.list_courses()


@router.post("/courses", status_code=status.HTTP_201_CREATED)
async def create_course(
    config_repo: ScheduleConfigRepoDep, response: Response, moderator: ModeratorDep, course: CourseConfig
) -> CourseConfig:
    saved, revision = config_repo.create_course(course)
    _set_revision_etag(response, revision)
    return saved


@router.get("/courses/{course_name:path}")
async def get_course(
    config_repo: ScheduleConfigRepoDep, course_name: str, _user_and_token: VerifyTokenDep
) -> CourseConfig:
    course = config_repo.get_course(course_name)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course not found: {course_name!r}")
    return course


@router.put("/courses/{course_name:path}")
async def update_course(
    config_repo: ScheduleConfigRepoDep,
    response: Response,
    moderator: ModeratorDep,
    course_name: str,
    course: CourseConfig,
) -> CourseConfig:
    saved, revision = config_repo.update_course(course_name, course)
    _set_revision_etag(response, revision)
    return saved


@router.delete("/courses/{course_name:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    config_repo: ScheduleConfigRepoDep, response: Response, moderator: ModeratorDep, course_name: str
) -> None:
    revision = config_repo.delete_course(course_name)
    _set_revision_etag(response, revision)


@router.get("/instructors")
async def list_instructors(
    config_repo: ScheduleConfigRepoDep, _user_and_token: VerifyTokenDep
) -> list[InstructorConfig.Instructor]:
    return config_repo.list_instructors()


@router.get("/instructors/meetings-counts")
async def instructor_meetings_counts(
    config_repo: ScheduleConfigRepoDep,
    _user_and_token: VerifyTokenDep,
    instructor_id: Annotated[list[str] | None, Query()] = None,
) -> InstructorMeetingsCountsResponse:
    """Count placed term meetings for instructors.

    Omit `instructor_id` to count all instructors; pass one or more ids to count selectively.
    """
    instructors = config_repo.list_instructors()
    if instructor_id is None:
        instructor_ids = [instructor.id for instructor in instructors]
    else:
        known = {instructor.id for instructor in instructors}
        instructor_ids = [item for item in instructor_id if item in known]
    counts = count_meetings_by_instructor(
        config_repo.list_courses(),
        config_repo.get_term(),
        instructor_ids,
    )
    return InstructorMeetingsCountsResponse(counts=counts)


@router.post("/instructors", status_code=status.HTTP_201_CREATED)
async def create_instructor(
    config_repo: ScheduleConfigRepoDep,
    response: Response,
    moderator: ModeratorDep,
    instructor: InstructorConfig.Instructor,
) -> InstructorConfig.Instructor:
    saved, revision = config_repo.create_instructor(instructor)
    _set_revision_etag(response, revision)
    return saved


@router.get("/instructors/{instructor_id:path}")
async def get_instructor(
    config_repo: ScheduleConfigRepoDep, instructor_id: str, _user_and_token: VerifyTokenDep
) -> InstructorConfig.Instructor:
    instructor = config_repo.get_instructor(instructor_id)
    if instructor is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Instructor not found: {instructor_id!r}")
    return instructor


@router.put("/instructors/{instructor_id:path}")
async def update_instructor(
    config_repo: ScheduleConfigRepoDep,
    response: Response,
    moderator: ModeratorDep,
    instructor_id: str,
    instructor: InstructorConfig.Instructor,
) -> InstructorConfig.Instructor:
    saved, revision = config_repo.update_instructor(instructor_id, instructor)
    _set_revision_etag(response, revision)
    return saved


@router.delete("/instructors/{instructor_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_instructor(
    config_repo: ScheduleConfigRepoDep, response: Response, moderator: ModeratorDep, instructor_id: str
) -> None:
    revision = config_repo.delete_instructor(instructor_id)
    _set_revision_etag(response, revision)


@router.get("/student-groups")
async def list_student_groups(
    config_repo: ScheduleConfigRepoDep, _user_and_token: VerifyTokenDep
) -> list[StudentsGroups]:
    return config_repo.list_student_groups()


@router.post("/student-groups", status_code=status.HTTP_201_CREATED)
async def create_student_group(
    config_repo: ScheduleConfigRepoDep, response: Response, moderator: ModeratorDep, group: StudentsGroups
) -> StudentsGroups:
    saved, revision = config_repo.create_student_group(group)
    _set_revision_etag(response, revision)
    return saved


@router.get("/student-groups/{code:path}")
async def get_student_group(
    config_repo: ScheduleConfigRepoDep, code: str, _user_and_token: VerifyTokenDep
) -> StudentsGroups:
    group = config_repo.get_student_group(code)
    if group is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student group not found: {code!r}")
    return group


@router.put("/student-groups/{code:path}")
async def update_student_group(
    config_repo: ScheduleConfigRepoDep,
    response: Response,
    moderator: ModeratorDep,
    code: str,
    group: StudentsGroups,
) -> StudentsGroups:
    saved, revision = config_repo.update_student_group(code, group)
    _set_revision_etag(response, revision)
    return saved


@router.delete("/student-groups/{code:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_student_group(
    config_repo: ScheduleConfigRepoDep, response: Response, moderator: ModeratorDep, code: str
) -> None:
    revision = config_repo.delete_student_group(code)
    _set_revision_etag(response, revision)


@router.get("/rooms")
async def list_rooms(config_repo: ScheduleConfigRepoDep, _user_and_token: VerifyTokenDep) -> list[RoomConfig.Room]:
    return config_repo.list_rooms()


@router.post("/rooms", status_code=status.HTTP_201_CREATED)
async def create_room(
    config_repo: ScheduleConfigRepoDep, response: Response, moderator: ModeratorDep, room: RoomConfig.Room
) -> RoomConfig.Room:
    saved, revision = config_repo.create_room(room)
    _set_revision_etag(response, revision)
    return saved


@router.get("/rooms/{room_id:path}")
async def get_room(
    config_repo: ScheduleConfigRepoDep, room_id: str, _user_and_token: VerifyTokenDep
) -> RoomConfig.Room:
    room = config_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Room not found: {room_id!r}")
    return room


@router.put("/rooms/{room_id:path}")
async def update_room(
    config_repo: ScheduleConfigRepoDep,
    response: Response,
    moderator: ModeratorDep,
    room_id: str,
    room: RoomConfig.Room,
) -> RoomConfig.Room:
    saved, revision = config_repo.update_room(room_id, room)
    _set_revision_etag(response, revision)
    return saved


@router.delete("/rooms/{room_id:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    config_repo: ScheduleConfigRepoDep, response: Response, moderator: ModeratorDep, room_id: str
) -> None:
    revision = config_repo.delete_room(room_id)
    _set_revision_etag(response, revision)
