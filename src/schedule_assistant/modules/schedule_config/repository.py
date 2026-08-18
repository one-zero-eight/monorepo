import uuid
from typing import Any, cast

import jsonpatch
from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from src.schedule_assistant.config import settings
from src.schedule_assistant.db.models import (
    ConfigHistoryEventRow,
    ConfigMetaRow,
    CourseRow,
    InstructorRow,
    RoomRow,
    StudentGroupRow,
    TermRow,
)
from src.schedule_assistant.db.session import get_engine
from src.schedule_assistant.modules.schedule_config.event_log import (
    ConfigChangeEvent,
    ConfigChangeEventSummary,
    ConfigResource,
)
from src.schedule_assistant.modules.schedule_config.schemas import (
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
    InstructorSlotPreferenceEntry,
    RoomConfig,
    ScheduleConfig,
    ScheduleConfigUpdate,
    SectionConfig,
    SectionsConfig,
    StudentsGroups,
    TermConfig,
    TermPartialUpdate,
)
from src.schedule_assistant.modules.schedule_config.validation import (
    ValidationContext,
    validate_course,
    validate_courses,
    validate_instructor,
    validate_instructor_delete,
    validate_instructors,
    validate_instructors_update,
    validate_room,
    validate_room_delete,
    validate_rooms,
    validate_rooms_update,
    validate_sections,
    validate_sections_update,
    validate_student_group,
    validate_student_group_delete,
    validate_term_config,
)
from src.schedule_assistant.utcnow import utcnow

TERM_SINGLETON_ID = 1
META_SINGLETON_ID = 1


def _section_payloads_from_stored(sections: object) -> list[Any]:
    if not isinstance(sections, list):
        return []
    allowed = set(SectionConfig.model_fields)
    payloads: list[Any] = []
    for section in sections:
        if isinstance(section, dict):
            payloads.append({key: value for key, value in section.items() if key in allowed})
            continue
        payloads.append(section)
    return payloads


def _course_row_payload(row: CourseRow) -> dict[str, Any]:
    return {
        "name": row.name,
        "section_code": row.section_code,
        "short_name": row.short_name,
        "name_ru": row.name_ru,
        "short_name_ru": row.short_name_ru,
        "instructors": row.instructors or [],
        "components": row.components,
    }


def _course_to_row(course: CourseConfig) -> CourseRow:
    return CourseRow(
        name=course.name,
        section_code=course.section_code,
        short_name=course.short_name,
        name_ru=course.name_ru,
        short_name_ru=course.short_name_ru,
        instructors=[item.model_dump(mode="json") for item in course.instructors],
        components=[component.model_dump(mode="json") for component in course.components],
    )


def _instructor_row_to_model(row: InstructorRow) -> InstructorConfig.Instructor:
    return InstructorConfig.Instructor(
        id=row.id,
        name_en=row.name_en,
        name_ru=row.name_ru,
        email=row.email,
        alias=row.alias,
        position=row.position,
        slot_preferences=[
            InstructorSlotPreferenceEntry.model_validate(entry) for entry in (row.slot_preferences or [])
        ],
    )


def _apply_instructor_fields(row: InstructorRow, instructor: InstructorConfig.Instructor) -> None:
    row.name_en = instructor.name_en
    row.name_ru = instructor.name_ru
    row.email = instructor.email
    row.alias = instructor.alias
    row.position = instructor.position
    row.slot_preferences = [entry.model_dump(mode="json") for entry in instructor.slot_preferences]


def _new_instructor_row(instructor: InstructorConfig.Instructor) -> InstructorRow:
    return InstructorRow(
        id=instructor.id,
        name_en=instructor.name_en,
        name_ru=instructor.name_ru,
        email=instructor.email,
        alias=instructor.alias,
        position=instructor.position,
        slot_preferences=[entry.model_dump(mode="json") for entry in instructor.slot_preferences],
    )


def _room_row_to_model(row: RoomRow) -> RoomConfig.Room:
    return RoomConfig.Room(
        id=row.id,
        name=row.name,
        capacity=row.capacity,
        features=dict(row.features or {}),
    )


def _new_room_row(room: RoomConfig.Room) -> RoomRow:
    return RoomRow(
        id=room.id,
        name=room.name,
        capacity=room.capacity,
        features=dict(room.features or {}),
    )


def _apply_room_fields(row: RoomRow, room: RoomConfig.Room) -> None:
    row.name = room.name
    row.capacity = room.capacity
    row.features = dict(room.features or {})


class ScheduleConfigRepository:
    def __init__(self, db_url: str | None = None) -> None:
        self.db_url = db_url or settings.db_url.get_secret_value()
        self._engine = get_engine(self.db_url)
        self._session_factory = sessionmaker(bind=self._engine, autoflush=False, autocommit=False)

    def _session(self) -> Session:
        return self._session_factory()

    def _model_dump(self, model: BaseModel) -> dict[str, Any]:
        return model.model_dump(mode="json", by_alias=True, exclude_none=True)

    def _get_revision_row(self, session: Session) -> ConfigMetaRow:
        row = session.get(ConfigMetaRow, META_SINGLETON_ID)
        if row is None:
            row = ConfigMetaRow(id=META_SINGLETON_ID, revision=0)
            session.add(row)
            session.flush()
        return row

    def get_revision(self) -> int:
        with self._session() as session:
            return self._get_revision_row(session).revision

    def _assembled_dump(self, session: Session) -> dict[str, Any]:
        return self._model_dump(self._assemble_config(session))

    def _assembled_dump_if_possible(self, session: Session) -> dict[str, Any]:
        if session.get(TermRow, TERM_SINGLETON_ID) is None:
            dump: dict[str, Any] = {}
            sections = self._load_sections_config(session)
            if sections.students_groups:
                dump["students_groups"] = self._model_dump(sections)["students_groups"]
            rooms = self._load_room_config(session)
            if rooms.rooms:
                dump["rooms"] = self._model_dump(rooms)["rooms"]
            instructors = self._load_instructor_config(session)
            if instructors.instructors:
                dump["instructors"] = self._model_dump(instructors)["instructors"]
            courses = self._load_courses_config(session)
            if courses.courses:
                dump["courses"] = self._model_dump(courses)["courses"]
            return dump
        return self._assembled_dump(session)

    def _append_history(
        self,
        session: Session,
        old_dump: dict[str, Any],
        new_dump: dict[str, Any],
        *,
        saved_by: str,
        resources: list[ConfigResource],
    ) -> int:
        if old_dump == new_dump:
            return self._get_revision_row(session).revision

        patch = jsonpatch.make_patch(old_dump, new_dump).patch
        if not patch:
            return self._get_revision_row(session).revision

        meta = self._get_revision_row(session)
        new_revision = meta.revision + 1
        meta.revision = new_revision
        session.add(
            ConfigHistoryEventRow(
                id=str(uuid.uuid4()),
                revision=new_revision,
                resources=resources,
                saved_at=utcnow().isoformat(),
                saved_by=saved_by,
                patch=patch,
                snapshot=new_dump,
            )
        )
        return new_revision

    def _load_term_config(self, session: Session) -> TermConfig | None:
        row = session.get(TermRow, TERM_SINGLETON_ID)
        if row is None:
            return None
        return self._term_row_to_term(row)

    def _validation_context(self, session: Session) -> ValidationContext:
        return ValidationContext(
            sections=self._load_sections_config(session),
            rooms=self._load_room_config(session),
            instructors=self._load_instructor_config(session),
            courses=self._load_courses_config(session),
            term=self._load_term_config(session),
        )

    def _raise_validation_errors(self, errors: list[str]) -> None:
        if errors:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"errors": errors},
            )

    def _term_row_to_term(self, row: TermRow) -> TermConfig:
        return TermConfig.model_validate(
            {
                "name": row.name,
                "semester": {"start_date": row.semester_start, "end_date": row.semester_end},
                "days": row.days,
                "starting_day": row.starting_day,
                "time_slots": row.time_slots,
                "sections": _section_payloads_from_stored(row.sections),
                "instructor_positions": row.instructor_positions or [],
                "course_instructor_roles": row.course_instructor_roles or [],
                "course_component_tags": row.course_component_tags or [],
                "room_attributes": row.room_attributes or [],
            }
        )

    def _term_to_row(self, term: TermConfig, row: TermRow | None = None) -> TermRow:
        payload = term.model_dump(mode="json")
        if row is None:
            row = TermRow(id=TERM_SINGLETON_ID)
        row.name = payload["name"]
        row.semester_start = term.semester.start_date
        row.semester_end = term.semester.end_date
        row.days = payload["days"]
        row.starting_day = payload["starting_day"]
        row.time_slots = payload["time_slots"]
        row.sections = payload["sections"]
        row.instructor_positions = payload.get("instructor_positions") or []
        row.course_instructor_roles = payload.get("course_instructor_roles") or []
        row.course_component_tags = payload.get("course_component_tags") or []
        row.room_attributes = payload.get("room_attributes") or []
        return row

    def _merge_term_partial(self, existing: TermConfig | None, partial: TermPartialUpdate) -> TermConfig:
        if existing is None:
            return TermConfig.model_validate(partial.model_dump(exclude_unset=True))
        merged = {**existing.model_dump(), **partial.model_dump(exclude_unset=True)}
        return TermConfig.model_validate(merged)

    def _load_term_row(self, session: Session) -> TermRow:
        row = session.get(TermRow, TERM_SINGLETON_ID)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Schedule config resource not found: term",
            )
        return row

    def _load_sections_config(self, session: Session) -> SectionsConfig:
        term_row = session.get(TermRow, TERM_SINGLETON_ID)
        sections = [
            SectionConfig.model_validate(section)
            for section in _section_payloads_from_stored(term_row.sections if term_row is not None else [])
        ]
        student_groups = [
            StudentsGroups(
                code=row.code,
                kind=row.kind,
                name=row.name,
                estimated_size=row.estimated_size,
                students=row.students,
            )
            for row in session.scalars(select(StudentGroupRow).order_by(StudentGroupRow.code)).all()
        ]
        return SectionsConfig(sections=sections, students_groups=student_groups)

    def _load_room_config(self, session: Session) -> RoomConfig:
        rooms = [_room_row_to_model(row) for row in session.scalars(select(RoomRow).order_by(RoomRow.id)).all()]
        return RoomConfig(rooms=rooms)

    def _load_instructor_config(self, session: Session) -> InstructorConfig:
        instructors = [
            _instructor_row_to_model(row)
            for row in session.scalars(select(InstructorRow).order_by(InstructorRow.id)).all()
        ]
        return InstructorConfig(instructors=instructors)

    def _load_courses_config(self, session: Session) -> CoursesConfig:
        courses = [
            CourseConfig.model_validate(_course_row_payload(row))
            for row in session.scalars(select(CourseRow).order_by(CourseRow.name)).all()
        ]
        return CoursesConfig(courses=courses)

    def _assemble_config(self, session: Session) -> ScheduleConfig:
        term = self._term_row_to_term(self._load_term_row(session))
        sections = self._load_sections_config(session)
        rooms = self._load_room_config(session)
        instructors = self._load_instructor_config(session)
        courses = self._load_courses_config(session)
        return ScheduleConfig(
            term=term,
            rooms=rooms.rooms,
            instructors=instructors.instructors,
            students_groups=sections.students_groups,
            courses=courses.courses,
        )

    def get_assembled(self) -> ScheduleConfig:
        with self._session() as session:
            return self._assemble_config(session)

    def get_term(self) -> TermConfig | None:
        with self._session() as session:
            row = session.get(TermRow, TERM_SINGLETON_ID)
            if row is None:
                return None
            return self._term_row_to_term(row)

    def set_term(self, term: TermConfig, *, saved_by: str) -> tuple[TermConfig, int]:
        with self._session() as session:
            old_dump = self._assembled_dump_if_possible(session)
            ctx = self._validation_context(session)
            self._raise_validation_errors(validate_term_config(term, ctx))
            row = session.get(TermRow, TERM_SINGLETON_ID)
            session.add(self._term_to_row(term, row))
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["term"],
            )
            session.commit()
            return self._term_row_to_term(self._load_term_row(session)), revision

    def get_sections(self) -> SectionsConfig:
        with self._session() as session:
            return self._load_sections_config(session)

    def set_sections(self, config: SectionsConfig, *, saved_by: str) -> tuple[SectionsConfig, int]:
        with self._session() as session:
            term_row = session.get(TermRow, TERM_SINGLETON_ID)
            if term_row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Schedule config resource not found: term"
                )
            old_dump = self._assembled_dump_if_possible(session)
            self._raise_validation_errors(validate_sections(config))
            term_row.sections = [section.model_dump(mode="json") for section in config.sections]
            session.execute(delete(StudentGroupRow))
            for group in config.students_groups:
                session.add(
                    StudentGroupRow(
                        code=group.code,
                        kind=group.kind,
                        name=group.name,
                        estimated_size=group.estimated_size,
                        students=group.students,
                    )
                )
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["sections"],
            )
            session.commit()
            return self._load_sections_config(session), revision

    def list_courses(self) -> list[CourseConfig]:
        return self.get_courses().courses

    def get_course(self, name: str) -> CourseConfig | None:
        with self._session() as session:
            row = session.get(CourseRow, name)
            if row is None:
                return None
            return CourseConfig.model_validate(_course_row_payload(row))

    def create_course(self, course: CourseConfig, *, saved_by: str) -> tuple[CourseConfig, int]:
        with self._session() as session:
            if session.get(CourseRow, course.name) is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=f"Course already exists: {course.name!r}"
                )
            old_dump = self._assembled_dump_if_possible(session)
            ctx = self._validation_context(session)
            self._raise_validation_errors(validate_course(course, ctx))
            session.add(_course_to_row(course))
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["courses"],
            )
            session.commit()
            return course, revision

    def update_course(self, name: str, course: CourseConfig, *, saved_by: str) -> tuple[CourseConfig, int]:
        with self._session() as session:
            row = session.get(CourseRow, name)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course not found: {name!r}")
            old_dump = self._assembled_dump_if_possible(session)
            ctx = self._validation_context(session)
            self._raise_validation_errors(validate_course(course, ctx, exclude_name=name))
            if course.name != name:
                if session.get(CourseRow, course.name) is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT, detail=f"Course already exists: {course.name!r}"
                    )
                session.delete(row)
                session.flush()
                session.add(_course_to_row(course))
            else:
                row.section_code = course.section_code
                row.short_name = course.short_name
                row.name_ru = course.name_ru
                row.short_name_ru = course.short_name_ru
                row.instructors = [item.model_dump(mode="json") for item in course.instructors]
                row.components = [component.model_dump(mode="json") for component in course.components]
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["courses"],
            )
            session.commit()
            return course, revision

    def delete_course(self, name: str, *, saved_by: str) -> int:
        with self._session() as session:
            row = session.get(CourseRow, name)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Course not found: {name!r}")
            old_dump = self._assembled_dump_if_possible(session)
            session.delete(row)
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["courses"],
            )
            session.commit()
            return revision

    def get_courses(self) -> CoursesConfig:
        with self._session() as session:
            return self._load_courses_config(session)

    def set_courses(self, config: CoursesConfig, *, saved_by: str) -> tuple[CoursesConfig, int]:
        with self._session() as session:
            old_dump = self._assembled_dump_if_possible(session)
            ctx = ValidationContext(
                sections=self._load_sections_config(session),
                rooms=self._load_room_config(session),
                instructors=self._load_instructor_config(session),
                courses=CoursesConfig(),
                term=self._load_term_config(session),
            )
            self._raise_validation_errors(validate_courses(config, ctx))
            session.execute(delete(CourseRow))
            for course in config.courses:
                session.add(_course_to_row(course))
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["courses"],
            )
            session.commit()
            return self._load_courses_config(session), revision

    def list_instructors(self) -> list[InstructorConfig.Instructor]:
        return self.get_instructors().instructors

    def get_instructor(self, instructor_id: str) -> InstructorConfig.Instructor | None:
        with self._session() as session:
            row = session.get(InstructorRow, instructor_id)
            if row is None:
                return None
            return _instructor_row_to_model(row)

    def create_instructor(
        self, instructor: InstructorConfig.Instructor, *, saved_by: str
    ) -> tuple[InstructorConfig.Instructor, int]:
        with self._session() as session:
            if session.get(InstructorRow, instructor.id) is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=f"Instructor already exists: {instructor.id!r}"
                )
            old_dump = self._assembled_dump_if_possible(session)
            self._raise_validation_errors(
                validate_instructor(
                    instructor,
                    self._load_instructor_config(session),
                    term=self._term_row_to_term(self._load_term_row(session)),
                )
            )
            session.add(_new_instructor_row(instructor))
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["instructors"],
            )
            session.commit()
            return instructor, revision

    def update_instructor(
        self,
        instructor_id: str,
        instructor: InstructorConfig.Instructor,
        *,
        saved_by: str,
    ) -> tuple[InstructorConfig.Instructor, int]:
        with self._session() as session:
            row = session.get(InstructorRow, instructor_id)
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Instructor not found: {instructor_id!r}"
                )
            old_dump = self._assembled_dump_if_possible(session)
            instructors = [
                item for item in self._load_instructor_config(session).instructors if item.id != instructor_id
            ]
            instructors.append(instructor)
            self._raise_validation_errors(
                validate_instructors(
                    InstructorConfig(instructors=instructors),
                    term=self._term_row_to_term(self._load_term_row(session)),
                )
            )
            if instructor.id != instructor_id:
                if session.get(InstructorRow, instructor.id) is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT, detail=f"Instructor already exists: {instructor.id!r}"
                    )
                session.delete(row)
                session.flush()
                row = InstructorRow(id=instructor.id)
                session.add(row)
            _apply_instructor_fields(row, instructor)
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["instructors"],
            )
            session.commit()
            return instructor, revision

    def delete_instructor(self, instructor_id: str, *, saved_by: str) -> int:
        with self._session() as session:
            row = session.get(InstructorRow, instructor_id)
            if row is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail=f"Instructor not found: {instructor_id!r}"
                )
            old_dump = self._assembled_dump_if_possible(session)
            ctx = self._validation_context(session)
            self._raise_validation_errors(validate_instructor_delete(instructor_id, ctx))
            session.delete(row)
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["instructors"],
            )
            session.commit()
            return revision

    def get_instructors(self) -> InstructorConfig:
        with self._session() as session:
            return self._load_instructor_config(session)

    def set_instructors(self, config: InstructorConfig, *, saved_by: str) -> tuple[InstructorConfig, int]:
        with self._session() as session:
            old_dump = self._assembled_dump_if_possible(session)
            self._raise_validation_errors(
                validate_instructors(config, term=self._term_row_to_term(self._load_term_row(session)))
            )
            session.execute(delete(InstructorRow))
            for instructor in config.instructors:
                session.add(_new_instructor_row(instructor))
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["instructors"],
            )
            session.commit()
            return self._load_instructor_config(session), revision

    def list_student_groups(self) -> list[StudentsGroups]:
        return self.get_sections().students_groups

    def get_student_group(self, code: str) -> StudentsGroups | None:
        with self._session() as session:
            row = session.get(StudentGroupRow, code)
            if row is None:
                return None
            return StudentsGroups(
                code=row.code,
                kind=row.kind,
                name=row.name,
                estimated_size=row.estimated_size,
                students=row.students,
            )

    def create_student_group(self, group: StudentsGroups, *, saved_by: str) -> tuple[StudentsGroups, int]:
        with self._session() as session:
            if session.get(StudentGroupRow, group.code) is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail=f"Student group already exists: {group.code!r}"
                )
            old_dump = self._assembled_dump_if_possible(session)
            ctx = self._validation_context(session)
            self._raise_validation_errors(validate_student_group(group, ctx))
            session.add(
                StudentGroupRow(
                    code=group.code,
                    kind=group.kind,
                    name=group.name,
                    estimated_size=group.estimated_size,
                    students=group.students,
                )
            )
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["sections"],
            )
            session.commit()
            return group, revision

    def update_student_group(self, code: str, group: StudentsGroups, *, saved_by: str) -> tuple[StudentsGroups, int]:
        with self._session() as session:
            row = session.get(StudentGroupRow, code)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student group not found: {code!r}")
            old_dump = self._assembled_dump_if_possible(session)
            ctx = self._validation_context(session)
            self._raise_validation_errors(validate_student_group(group, ctx, exclude_code=code))
            if group.code != code:
                if session.get(StudentGroupRow, group.code) is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT, detail=f"Student group already exists: {group.code!r}"
                    )
                session.delete(row)
                session.flush()
                row = StudentGroupRow(code=group.code)
                session.add(row)
            row.kind = group.kind
            row.name = group.name
            row.estimated_size = group.estimated_size
            row.students = group.students
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["sections"],
            )
            session.commit()
            return group, revision

    def delete_student_group(self, code: str, *, saved_by: str) -> int:
        with self._session() as session:
            row = session.get(StudentGroupRow, code)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Student group not found: {code!r}")
            old_dump = self._assembled_dump_if_possible(session)
            ctx = self._validation_context(session)
            self._raise_validation_errors(validate_student_group_delete(code, ctx))
            session.delete(row)
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["sections"],
            )
            session.commit()
            return revision

    def replace_student_group_students(
        self,
        updates: dict[str, list[str]],
        *,
        saved_by: str,
    ) -> int:
        """Replace ``students`` lists for the given group codes in one history revision."""
        if not updates:
            return self.get_revision()

        with self._session() as session:
            old_dump = self._assembled_dump_if_possible(session)
            for code, students in updates.items():
                row = session.get(StudentGroupRow, code)
                if row is None:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Student group not found: {code!r}",
                    )
                row.students = list(students)
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["sections"],
            )
            session.commit()
            return revision

    def list_rooms(self) -> list[RoomConfig.Room]:
        return self.get_rooms().rooms

    def get_room(self, room_id: str) -> RoomConfig.Room | None:
        with self._session() as session:
            row = session.get(RoomRow, room_id)
            if row is None:
                return None
            return _room_row_to_model(row)

    def create_room(self, room: RoomConfig.Room, *, saved_by: str) -> tuple[RoomConfig.Room, int]:
        with self._session() as session:
            if session.get(RoomRow, room.id) is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Room already exists: {room.id!r}")
            old_dump = self._assembled_dump_if_possible(session)
            self._raise_validation_errors(
                validate_room(
                    room,
                    self._load_room_config(session),
                    courses=self._load_courses_config(session),
                    term=self._load_term_config(session),
                ),
            )
            session.add(_new_room_row(room))
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["rooms"],
            )
            session.commit()
            return room, revision

    def update_room(self, room_id: str, room: RoomConfig.Room, *, saved_by: str) -> tuple[RoomConfig.Room, int]:
        with self._session() as session:
            row = session.get(RoomRow, room_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Room not found: {room_id!r}")
            old_dump = self._assembled_dump_if_possible(session)
            rooms = [item for item in self._load_room_config(session).rooms if item.id != room_id]
            rooms.append(room)
            self._raise_validation_errors(
                validate_rooms(
                    RoomConfig(rooms=rooms),
                    courses=self._load_courses_config(session),
                    term=self._load_term_config(session),
                ),
            )
            if room.id != room_id:
                if session.get(RoomRow, room.id) is not None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT, detail=f"Room already exists: {room.id!r}"
                    )
                session.delete(row)
                session.flush()
                row = _new_room_row(room)
                session.add(row)
            else:
                _apply_room_fields(row, room)
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["rooms"],
            )
            session.commit()
            return room, revision

    def delete_room(self, room_id: str, *, saved_by: str) -> int:
        with self._session() as session:
            row = session.get(RoomRow, room_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Room not found: {room_id!r}")
            old_dump = self._assembled_dump_if_possible(session)
            ctx = self._validation_context(session)
            self._raise_validation_errors(validate_room_delete(room_id, ctx))
            session.delete(row)
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["rooms"],
            )
            session.commit()
            return revision

    def get_rooms(self) -> RoomConfig:
        with self._session() as session:
            return self._load_room_config(session)

    def set_rooms(self, config: RoomConfig, *, saved_by: str) -> tuple[RoomConfig, int]:
        with self._session() as session:
            old_dump = self._assembled_dump_if_possible(session)
            ctx = ValidationContext(
                sections=self._load_sections_config(session),
                rooms=RoomConfig(),
                instructors=self._load_instructor_config(session),
                courses=self._load_courses_config(session),
            )
            self._raise_validation_errors(
                validate_rooms(config, courses=ctx.courses, term=self._load_term_config(session))
            )
            session.execute(delete(RoomRow))
            for room in config.rooms:
                session.add(_new_room_row(room))
            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=["rooms"],
            )
            session.commit()
            return self._load_room_config(session), revision

    def list_history(self) -> list[ConfigChangeEventSummary]:
        with self._session() as session:
            rows = session.scalars(select(ConfigHistoryEventRow).order_by(ConfigHistoryEventRow.revision.desc())).all()
            return [
                ConfigChangeEventSummary(
                    id=row.id,
                    revision=row.revision,
                    resources=cast(list[ConfigResource], row.resources),
                    saved_at=row.saved_at,
                    saved_by=row.saved_by,
                    change_count=len(row.patch),
                )
                for row in rows
            ]

    def get_history_event(self, event_id: str) -> ConfigChangeEvent:
        with self._session() as session:
            row = session.get(ConfigHistoryEventRow, event_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History event not found")
            return ConfigChangeEvent(
                id=row.id,
                revision=row.revision,
                resources=cast(list[ConfigResource], row.resources),
                saved_at=row.saved_at,
                saved_by=row.saved_by,
                patch=row.patch,
                snapshot="",
            )

    def get_history_snapshot(self, event_id: str) -> ScheduleConfig:
        with self._session() as session:
            row = session.get(ConfigHistoryEventRow, event_id)
            if row is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History event not found")
            snapshot = row.snapshot if isinstance(row.snapshot, dict) else {}
            return ScheduleConfig.model_validate(snapshot)

    def _resources_to_update(self, update: ScheduleConfigUpdate) -> set[ConfigResource]:
        resources: set[ConfigResource] = set()
        if update.term is not None:
            resources.add("term")
        if update.students_groups is not None:
            resources.add("sections")
        if update.courses is not None:
            resources.add("courses")
        if update.rooms is not None:
            resources.add("rooms")
        if update.instructors is not None:
            resources.add("instructors")
        return resources

    def _sections_config_from_update(
        self,
        existing: SectionsConfig,
        update: ScheduleConfigUpdate,
        *,
        merged_term: TermConfig | None = None,
    ) -> SectionsConfig:
        sections = merged_term.sections if merged_term is not None else existing.sections
        return SectionsConfig(
            sections=sections,
            students_groups=existing.students_groups if update.students_groups is None else update.students_groups,
        )

    def _apply_term_update(self, session: Session, term: TermConfig) -> None:
        row = session.get(TermRow, TERM_SINGLETON_ID)
        session.add(self._term_to_row(term, row))

    def _apply_student_groups_update(self, session: Session, students_groups: list[StudentsGroups]) -> None:
        session.execute(delete(StudentGroupRow))
        for group in students_groups:
            session.add(
                StudentGroupRow(
                    code=group.code,
                    kind=group.kind,
                    name=group.name,
                    estimated_size=group.estimated_size,
                    students=group.students,
                )
            )

    def _apply_rooms_update(self, session: Session, rooms: list[RoomConfig.Room]) -> None:
        session.execute(delete(RoomRow))
        for room in rooms:
            session.add(_new_room_row(room))

    def _apply_instructors_update(self, session: Session, instructors: list[InstructorConfig.Instructor]) -> None:
        session.execute(delete(InstructorRow))
        for instructor in instructors:
            session.add(_new_instructor_row(instructor))

    def _apply_courses_update(self, session: Session, courses: list[CourseConfig]) -> None:
        session.execute(delete(CourseRow))
        for course in courses:
            session.add(_course_to_row(course))

    def set_config(
        self,
        update: ScheduleConfigUpdate,
        *,
        saved_by: str,
    ) -> tuple[ScheduleConfig, int]:
        resources = self._resources_to_update(update)
        if not resources:
            return self.get_assembled(), self.get_revision()

        with self._session() as session:
            old_dump = self._assembled_dump_if_possible(session)
            existing_sections = self._load_sections_config(session)
            existing_rooms = self._load_room_config(session)
            existing_instructors = self._load_instructor_config(session)
            existing_courses = self._load_courses_config(session)

            term_row = session.get(TermRow, TERM_SINGLETON_ID)
            existing_term = self._term_row_to_term(term_row) if term_row is not None else None
            merged_term = (
                self._merge_term_partial(existing_term, update.term) if update.term is not None else existing_term
            )
            new_sections = self._sections_config_from_update(
                existing_sections,
                update,
                merged_term=merged_term,
            )
            new_rooms = RoomConfig(rooms=update.rooms) if update.rooms is not None else existing_rooms
            new_instructors = (
                InstructorConfig(instructors=update.instructors)
                if update.instructors is not None
                else existing_instructors
            )
            new_courses = CoursesConfig(courses=update.courses) if update.courses is not None else existing_courses
            validation_context = ValidationContext(
                sections=new_sections,
                rooms=new_rooms,
                instructors=new_instructors,
                courses=new_courses,
                term=merged_term,
            )

            errors: list[str] = []
            changed_resources: list[ConfigResource] = []
            if "term" in resources:
                assert merged_term is not None
                errors.extend(validate_term_config(merged_term, validation_context))
                changed_resources.append("term")
            if "sections" in resources:
                errors.extend(validate_sections_update(existing_sections, new_sections, courses=new_courses))
                changed_resources.append("sections")
            if "rooms" in resources:
                errors.extend(
                    validate_rooms_update(
                        existing_rooms,
                        new_rooms,
                        courses=new_courses,
                        term=merged_term,
                    )
                )
                changed_resources.append("rooms")
            if "instructors" in resources:
                errors.extend(
                    validate_instructors_update(
                        existing_instructors,
                        new_instructors,
                        courses=new_courses,
                        term=merged_term,
                    )
                )
                changed_resources.append("instructors")
            if "courses" in resources:
                errors.extend(validate_courses(new_courses, validation_context))
                changed_resources.append("courses")
            self._raise_validation_errors(errors)

            if merged_term is not None and "term" in resources:
                self._apply_term_update(session, merged_term)
            if update.students_groups is not None:
                self._apply_student_groups_update(session, update.students_groups)
            if update.rooms is not None:
                self._apply_rooms_update(session, update.rooms)
            if update.instructors is not None:
                self._apply_instructors_update(session, update.instructors)
            if update.courses is not None:
                self._apply_courses_update(session, update.courses)

            session.flush()
            revision = self._append_history(
                session,
                old_dump,
                self._assembled_dump_if_possible(session),
                saved_by=saved_by,
                resources=changed_resources,
            )
            session.commit()
            return self._assemble_config(session), revision


schedule_config_repository = ScheduleConfigRepository()
