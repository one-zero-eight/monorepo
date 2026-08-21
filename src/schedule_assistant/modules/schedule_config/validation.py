import datetime as dtm
from collections.abc import Iterable
from dataclasses import dataclass

from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    InstructorConfig,
    InstructorSlotPreferenceLevel,
    RoomAttributeDef,
    RoomConfig,
    SectionsConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
    WeeklyPatternSlot,
)

VIRTUAL_ROOM_ID = "ONLINE"


def _is_virtual_room_id(room_id: str) -> bool:
    return room_id == VIRTUAL_ROOM_ID


@dataclass(frozen=True)
class ValidationContext:
    sections: SectionsConfig
    rooms: RoomConfig
    instructors: InstructorConfig
    courses: CoursesConfig
    term: TermConfig | None = None


def find_duplicates(values: Iterable[str]) -> list[str]:
    seen: dict[str, str] = {}
    duplicates: list[str] = []
    for value in values:
        if not value:
            continue
        key = value.casefold()
        if key in seen and seen[key] not in duplicates:
            duplicates.append(value)
        seen[key] = value
    return duplicates


def build_selector_map(sections: SectionsConfig) -> dict[str, set[str]]:
    selector_map: dict[str, set[str]] = {}
    for section in sections.sections:
        for program in section.programs:
            program_groups: set[str] = set(program.groups)
            for track in program.tracks:
                if track.groups:
                    groups = set(track.groups)
                    selector_map[f"@{program.code}/{track.name}"] = groups
                    program_groups.update(groups)
            if program_groups:
                selector_map[f"@{program.code}"] = program_groups
    return selector_map


def expand_group_tokens(tokens: list[str], selector_map: dict[str, set[str]]) -> set[str]:
    expanded: set[str] = set()
    for token in tokens:
        if token in selector_map:
            expanded.update(selector_map[token])
        else:
            expanded.add(token)
    return expanded


def collect_student_group_codes(sections: SectionsConfig) -> set[str]:
    return {group.code for group in sections.students_groups}


def collect_section_codes(sections: SectionsConfig) -> set[str]:
    return {str(section.code or "").strip() for section in sections.sections if str(section.code or "").strip()}


def groups_in_section(sections: SectionsConfig, section_code: str) -> set[str]:
    target = section_code.strip()
    groups: set[str] = set()
    for section in sections.sections:
        if str(section.code or "").strip() != target:
            continue
        for program in section.programs:
            groups.update(str(group or "").strip() for group in program.groups if str(group or "").strip())
            for track in program.tracks:
                groups.update(str(group or "").strip() for group in track.groups if str(group or "").strip())
    return groups


def collect_instructor_ids(instructors: InstructorConfig) -> set[str]:
    return {instructor.id for instructor in instructors.instructors}


def collect_room_ids(rooms: RoomConfig) -> set[str]:
    return {room.id for room in rooms.rooms}


def _collect_instructor_pool_ids(pool: list[str | list[str]]) -> set[str]:
    ids: set[str] = set()
    for entry in pool:
        if isinstance(entry, list):
            ids.update(entry)
        else:
            ids.add(entry)
    return ids


def _collect_meeting_instructor_ids(instructor: str | list[str] | None) -> set[str]:
    if instructor is None:
        return set()
    if isinstance(instructor, list):
        return {value.strip() for value in instructor if value and value.strip()}
    stripped = instructor.strip()
    return {stripped} if stripped else set()


def _collect_session_instructor_ids(session: ComponentSessionSeries) -> set[str]:
    ids: set[str] = set()
    if session.occurrences:
        for occurrence in session.occurrences:
            ids.update(_collect_meeting_instructor_ids(occurrence.instructor))
    if session.weekly_pattern:
        for slot in session.weekly_pattern:
            ids.update(_collect_meeting_instructor_ids(slot.instructor))
            if slot.edits:
                for edit in slot.edits:
                    ids.update(_collect_meeting_instructor_ids(edit.instructor))
    return ids


def _collect_session_room_ids(session: ComponentSessionSeries) -> set[str]:
    rooms: set[str] = set()
    if session.occurrences:
        for occurrence in session.occurrences:
            if occurrence.room:
                rooms.add(occurrence.room)
    if session.weekly_pattern:
        for slot in session.weekly_pattern:
            if slot.room:
                rooms.add(slot.room)
            if slot.edits:
                for edit in slot.edits:
                    if edit.room:
                        rooms.add(edit.room)
    return rooms


@dataclass(frozen=True)
class CourseReferences:
    group_tokens: set[str]
    instructor_ids: set[str]
    room_ids: set[str]


def collect_course_references(courses: CoursesConfig) -> CourseReferences:
    group_tokens: set[str] = set()
    instructor_ids: set[str] = set()
    room_ids: set[str] = set()
    for course in courses.courses:
        for component in course.components:
            group_tokens.update(component.student_groups)
            instructor_ids.update(_collect_instructor_pool_ids(component.instructor_pool))
            if component.sessions:
                for session in component.sessions:
                    group_tokens.update(session.audience)
                    instructor_ids.update(_collect_session_instructor_ids(session))
                    room_ids.update(_collect_session_room_ids(session))
    return CourseReferences(
        group_tokens=group_tokens,
        instructor_ids=instructor_ids,
        room_ids=room_ids,
    )


def _is_known_group_token(token: str, group_codes: set[str], selector_map: dict[str, set[str]]) -> bool:
    if token.startswith("@"):
        return token in selector_map
    return token in group_codes


def _is_known_room_id(room_id: str, room_ids: set[str]) -> bool:
    return room_id in room_ids or _is_virtual_room_id(room_id)


def _validate_occurrence_times(path: str, occurrence: SessionOccurrence, errors: list[str]) -> None:
    if occurrence.start_time >= occurrence.end_time:
        errors.append(f"{path}: start_time must be before end_time")


def _validate_weekly_slot_times(path: str, slot: WeeklyPatternSlot, errors: list[str]) -> None:
    if slot.start_time >= slot.end_time:
        errors.append(f"{path}: start_time must be before end_time")


def validate_term(term: TermConfig) -> list[str]:
    errors: list[str] = []
    if term.semester.start_date > term.semester.end_date:
        errors.append("term.semester.start_date must be on or before end_date")
    for index, slot in enumerate(term.time_slots):
        if slot.start_time >= slot.end_time:
            errors.append(f"term.time_slots[{index}]: start_time must be before end_time")
    errors.extend(_validate_room_attribute_defs(term.room_attributes))
    return errors


def _validate_room_attribute_defs(defs: list[RoomAttributeDef]) -> list[str]:
    errors: list[str] = []
    seen_keys: set[str] = set()
    for index, attr in enumerate(defs):
        path = f"term.room_attributes[{index}]"
        key = attr.key.strip()
        if not key:
            errors.append(f"{path}.key must not be empty")
        elif key in seen_keys:
            errors.append(f"{path}.key {key!r} is duplicated")
        else:
            seen_keys.add(key)

        if attr.type == "enum":
            values = [value.strip() for value in attr.enum_values]
            if not any(values):
                errors.append(f"{path}.enum_values must not be empty when type is enum")
            empty_indexes = [i for i, value in enumerate(attr.enum_values) if not value.strip()]
            for empty_index in empty_indexes:
                errors.append(f"{path}.enum_values[{empty_index}] must not be empty")
    return errors


def _feature_value_matches_type(value: bool | str | int | list[str], attr_type: str) -> bool:
    if attr_type == "boolean":
        return isinstance(value, bool)
    if attr_type == "string" or attr_type == "enum":
        return isinstance(value, str)
    if attr_type == "number":
        return isinstance(value, int) and not isinstance(value, bool)
    if attr_type == "list":
        return isinstance(value, list) and all(isinstance(item, str) for item in value)
    return False


def _validate_room_features(
    room: RoomConfig.Room,
    *,
    path: str,
    attribute_defs: list[RoomAttributeDef],
) -> list[str]:
    if not attribute_defs:
        return []
    errors: list[str] = []
    by_key = {attr.key: attr for attr in attribute_defs if attr.key.strip()}
    for key, value in room.features.items():
        attr = by_key.get(key)
        if attr is None:
            errors.append(f"{path}.features has unknown key {key!r}")
            continue
        if not _feature_value_matches_type(value, attr.type):
            errors.append(f"{path}.features[{key!r}] has invalid type for {attr.type}")
            continue
        if attr.type == "enum" and isinstance(value, str) and value not in attr.enum_values:
            errors.append(f"{path}.features[{key!r}] value {value!r} is not in enum_values")
        if attr.type == "list" and isinstance(value, list):
            empty_indexes = [i for i, item in enumerate(value) if not item.strip()]
            for empty_index in empty_indexes:
                errors.append(f"{path}.features[{key!r}][{empty_index}] must not be empty")
    return errors


def validate_rooms(
    config: RoomConfig,
    *,
    courses: CoursesConfig,
    term: TermConfig | None = None,
) -> list[str]:
    errors: list[str] = []
    room_ids = [room.id for room in config.rooms]
    errors.extend(f"Duplicate room id: {room_id!r}" for room_id in find_duplicates(room_ids))
    attribute_defs = term.room_attributes if term is not None else []
    for index, room in enumerate(config.rooms):
        if not room.id.strip():
            errors.append(f"rooms[{index}].id must not be empty")
        errors.extend(_validate_room_features(room, path=f"rooms[{index}]", attribute_defs=attribute_defs))
    return errors


def validate_rooms_update(
    old: RoomConfig,
    new: RoomConfig,
    *,
    courses: CoursesConfig,
    term: TermConfig | None = None,
) -> list[str]:
    errors = validate_rooms(new, courses=courses, term=term)
    removed_ids = collect_room_ids(old) - collect_room_ids(new)
    referenced_ids = {
        room_id for room_id in collect_course_references(courses).room_ids if not _is_virtual_room_id(room_id)
    }
    for room_id in sorted(removed_ids):
        if room_id in referenced_ids:
            errors.append(f"Cannot remove room {room_id!r}: still referenced in courses")
    return errors


def _validate_instructor_slot_preferences(
    instructor: InstructorConfig.Instructor,
    term: TermConfig,
    *,
    path_prefix: str = "slot_preferences",
) -> list[str]:
    errors: list[str] = []
    teaching_day_names = set(teaching_days_from_term_config(term))
    slot_starts = {slot.start_time for slot in term.time_slots}
    seen: set[tuple[str, dtm.time]] = set()
    for index, entry in enumerate(instructor.slot_preferences):
        prefix = f"{path_prefix}[{index}]"
        day_name = entry.weekday.value
        if day_name not in teaching_day_names:
            errors.append(f"{prefix}.weekday {day_name!r} is not in term.days")
        if entry.start_time not in slot_starts:
            errors.append(f"{prefix}.start_time {entry.start_time!r} does not match any term.time_slots start_time")
        key = (day_name, entry.start_time)
        if key in seen:
            errors.append(f"{prefix}: duplicate weekday+start_time ({day_name!r}, {entry.start_time!r})")
        seen.add(key)
        if entry.level == InstructorSlotPreferenceLevel.NEUTRAL:
            errors.append(f"{prefix}.level should be omitted instead of neutral")
    return errors


def teaching_days_from_term_config(term: TermConfig) -> list[str]:
    configured_days = list(dict.fromkeys(term.days))
    if not configured_days:
        return []
    start_day = term.starting_day
    if start_day not in configured_days:
        return [day.value for day in configured_days]
    start_idx = configured_days.index(start_day)
    ordered = configured_days[start_idx:] + configured_days[:start_idx]
    return [day.value for day in ordered]


def validate_instructors(config: InstructorConfig, *, term: TermConfig | None = None) -> list[str]:
    errors: list[str] = []
    instructor_ids = [instructor.id for instructor in config.instructors]
    errors.extend(f"Duplicate instructor id: {instructor_id!r}" for instructor_id in find_duplicates(instructor_ids))
    allowed_positions = [
        position for position in (term.instructor_positions if term is not None else []) if position.strip()
    ]
    for index, instructor in enumerate(config.instructors):
        if not instructor.id.strip():
            errors.append(f"instructors[{index}].id must not be empty")
        position = (instructor.position or "").strip()
        if allowed_positions and position and position not in allowed_positions:
            errors.append(f"instructors[{index}].position {position!r} is not in term.instructor_positions")
        if term is not None:
            errors.extend(
                _validate_instructor_slot_preferences(
                    instructor,
                    term,
                    path_prefix=f"instructors[{index}].slot_preferences",
                )
            )
    return errors


def validate_instructors_update(
    old: InstructorConfig,
    new: InstructorConfig,
    *,
    courses: CoursesConfig,
    term: TermConfig | None = None,
) -> list[str]:
    errors = validate_instructors(new, term=term)
    removed_ids = collect_instructor_ids(old) - collect_instructor_ids(new)
    referenced_ids = collect_course_references(courses).instructor_ids
    for instructor_id in sorted(removed_ids):
        if instructor_id in referenced_ids:
            errors.append(f"Cannot remove instructor {instructor_id!r}: still referenced in courses")
    return errors


def validate_sections(config: SectionsConfig) -> list[str]:
    errors: list[str] = []
    group_codes = collect_student_group_codes(config)

    section_codes = [section.code for section in config.sections]
    errors.extend(f"Duplicate section code: {code!r}" for code in find_duplicates(section_codes))

    students_group_codes = [group.code for group in config.students_groups]
    errors.extend(f"Duplicate students_groups code: {code!r}" for code in find_duplicates(students_group_codes))

    program_codes: list[str] = []
    for section_index, section in enumerate(config.sections):
        if not section.code.strip():
            errors.append(f"sections[{section_index}].code must not be empty")
        for program_index, program in enumerate(section.programs):
            program_codes.append(program.code)
            if not program.code.strip():
                errors.append(f"sections[{section_index}].programs[{program_index}].code must not be empty")
            track_codes = [track.code for track in program.tracks]
            errors.extend(
                f"Duplicate track code in program {program.code!r}: {code!r}" for code in find_duplicates(track_codes)
            )
            for group_code in program.groups:
                if group_code not in group_codes:
                    errors.append(
                        f"sections[{section_index}].programs[{program_index}].groups references unknown group {group_code!r}",
                    )
            for track_index, track in enumerate(program.tracks):
                for group_code in track.groups:
                    if group_code not in group_codes:
                        errors.append(
                            f"sections[{section_index}].programs[{program_index}].tracks[{track_index}].groups "
                            f"references unknown group {group_code!r}",
                        )
            if program.time_slots:
                for slot_index, slot in enumerate(program.time_slots):
                    if slot.start_time >= slot.end_time:
                        errors.append(
                            f"sections[{section_index}].programs[{program_index}].time_slots[{slot_index}]: "
                            "start_time must be before end_time",
                        )
            if program.semester is not None and program.semester.start_date > program.semester.end_date:
                errors.append(
                    f"sections[{section_index}].programs[{program_index}].semester.start_date "
                    "must be on or before end_date",
                )

    errors.extend(f"Duplicate program code: {code!r}" for code in find_duplicates(program_codes))
    return errors


def validate_sections_update(
    old: SectionsConfig,
    new: SectionsConfig,
    *,
    courses: CoursesConfig,
) -> list[str]:
    errors = validate_sections(new)
    removed_codes = collect_student_group_codes(old) - collect_student_group_codes(new)
    referenced_tokens = collect_course_references(courses).group_tokens
    selector_map = build_selector_map(new)
    referenced_group_codes: set[str] = set()
    for token in referenced_tokens:
        referenced_group_codes.update(expand_group_tokens([token], selector_map))
        if not token.startswith("@"):
            referenced_group_codes.add(token)
    for group_code in sorted(removed_codes):
        if group_code in referenced_group_codes:
            errors.append(f"Cannot remove students_groups entry {group_code!r}: still referenced in courses")
    return errors


def validate_courses(config: CoursesConfig, ctx: ValidationContext) -> list[str]:
    errors: list[str] = []
    group_codes = collect_student_group_codes(ctx.sections)
    selector_map = build_selector_map(ctx.sections)
    instructor_ids = collect_instructor_ids(ctx.instructors)
    room_ids = collect_room_ids(ctx.rooms)

    course_names = [course.name for course in config.courses]
    errors.extend(f"Duplicate course name: {name!r}" for name in find_duplicates(course_names))

    for course_index, course in enumerate(config.courses):
        course_path = f"courses[{course_index}]"
        section_code = course.section_code.strip()
        if not section_code:
            errors.append(f"{course_path}.section_code must not be empty")
            section_groups: set[str] = set()
        else:
            section_codes = collect_section_codes(ctx.sections)
            if section_code not in section_codes:
                errors.append(
                    f"{course_path}.section_code references unknown section {section_code!r}",
                )
            section_groups = groups_in_section(ctx.sections, section_code)

        assignment_ids = [item.id for item in course.instructors]
        errors.extend(
            f"{course_path}.instructors duplicate instructor id: {item_id!r}"
            for item_id in find_duplicates(assignment_ids)
        )
        allowed_roles = [
            role for role in (ctx.term.course_instructor_roles if ctx.term is not None else []) if role.strip()
        ]
        allowed_tags = [tag for tag in (ctx.term.course_component_tags if ctx.term is not None else []) if tag.strip()]
        for assignment_index, assignment in enumerate(course.instructors):
            assignment_path = f"{course_path}.instructors[{assignment_index}]"
            if not assignment.id.strip():
                errors.append(f"{assignment_path}.id must not be empty")
            elif assignment.id not in instructor_ids:
                errors.append(f"{assignment_path}.id references unknown instructor {assignment.id!r}")
            role = assignment.role.strip()
            if not role:
                errors.append(f"{assignment_path}.role must not be empty")
            elif allowed_roles and role not in allowed_roles:
                errors.append(f"{assignment_path}.role {role!r} is not in term.course_instructor_roles")

        component_count = len(course.components)
        for component_index, component in enumerate(course.components):
            path = f"{course_path}.components[{component_index}]"
            tag = str(component.tag or "").strip()
            if allowed_tags and tag and tag not in allowed_tags:
                errors.append(f"{path}.tag {tag!r} is not in term.course_component_tags")
            for token in component.student_groups:
                if not _is_known_group_token(token, group_codes, selector_map):
                    errors.append(f"{path}.student_groups references unknown group or selector {token!r}")
                    continue
                expanded = expand_group_tokens([token], selector_map)
                if not expanded.issubset(section_groups):
                    errors.append(
                        f"{path}.student_groups token {token!r} is outside section {section_code!r}",
                    )

            component_groups = expand_group_tokens(component.student_groups, selector_map)

            for pool_id in _collect_instructor_pool_ids(component.instructor_pool):
                if pool_id not in instructor_ids:
                    errors.append(f"{path}.instructor_pool references unknown instructor {pool_id!r}")

            relates_to = component.relates_to
            if relates_to is not None:
                indices = [relates_to] if isinstance(relates_to, int) else relates_to
                for relates_index in indices:
                    if relates_index < 0 or relates_index >= component_count:
                        errors.append(
                            f"{path}.relates_to references invalid component index {relates_index}",
                        )

            if not component.sessions:
                continue

            for session_index, session in enumerate(component.sessions):
                session_path = f"{path}.sessions[{session_index}]"
                session_groups = expand_group_tokens(session.audience, selector_map)
                if session.audience and not session_groups.issubset(component_groups):
                    errors.append(f"{session_path}.audience must be a subset of component student_groups")
                for audience_token in session.audience:
                    if not _is_known_group_token(audience_token, group_codes, selector_map):
                        errors.append(
                            f"{session_path}.audience references unknown group or selector {audience_token!r}",
                        )
                        continue
                    expanded = expand_group_tokens([audience_token], selector_map)
                    if not expanded.issubset(section_groups):
                        errors.append(
                            f"{session_path}.audience token {audience_token!r} is outside section {section_code!r}",
                        )

                if session.occurrences:
                    for occurrence_index, occurrence in enumerate(session.occurrences):
                        occurrence_path = f"{session_path}.occurrences[{occurrence_index}]"
                        _validate_occurrence_times(occurrence_path, occurrence, errors)
                        if occurrence.room and not _is_known_room_id(occurrence.room, room_ids):
                            errors.append(
                                f"{occurrence_path}.room references unknown room {occurrence.room!r}",
                            )
                        for meeting_instructor_id in _collect_meeting_instructor_ids(occurrence.instructor):
                            if meeting_instructor_id not in instructor_ids:
                                errors.append(
                                    f"{occurrence_path}.instructor references unknown instructor {meeting_instructor_id!r}",
                                )

                if session.weekly_pattern:
                    for slot_index, slot in enumerate(session.weekly_pattern):
                        slot_path = f"{session_path}.weekly_pattern[{slot_index}]"
                        _validate_weekly_slot_times(slot_path, slot, errors)
                        if slot.room and not _is_known_room_id(slot.room, room_ids):
                            errors.append(f"{slot_path}.room references unknown room {slot.room!r}")
                        for meeting_instructor_id in _collect_meeting_instructor_ids(slot.instructor):
                            if meeting_instructor_id not in instructor_ids:
                                errors.append(
                                    f"{slot_path}.instructor references unknown instructor {meeting_instructor_id!r}",
                                )
                        if slot.edits:
                            for edit_index, edit in enumerate(slot.edits):
                                edit_path = f"{slot_path}.edits[{edit_index}]"
                                if edit.room and not _is_known_room_id(edit.room, room_ids):
                                    errors.append(f"{edit_path}.room references unknown room {edit.room!r}")
                                for meeting_instructor_id in _collect_meeting_instructor_ids(edit.instructor):
                                    if meeting_instructor_id not in instructor_ids:
                                        errors.append(
                                            f"{edit_path}.instructor references unknown instructor {meeting_instructor_id!r}",
                                        )

    return errors


def validate_term_config(term: TermConfig, ctx: ValidationContext) -> list[str]:
    errors = validate_term(term)
    errors.extend(
        validate_sections(
            SectionsConfig(sections=term.sections, students_groups=ctx.sections.students_groups),
        )
    )
    return errors


def validate_course(course: CourseConfig, ctx: ValidationContext, *, exclude_name: str | None = None) -> list[str]:
    other_courses = [item for item in ctx.courses.courses if item.name != exclude_name]
    return validate_courses(CoursesConfig(courses=[*other_courses, course]), ctx)


def validate_instructor(
    instructor: InstructorConfig.Instructor,
    instructors: InstructorConfig,
    *,
    term: TermConfig | None = None,
) -> list[str]:
    return validate_instructors(InstructorConfig(instructors=[*instructors.instructors, instructor]), term=term)


def validate_room(
    room: RoomConfig.Room,
    rooms: RoomConfig,
    *,
    courses: CoursesConfig,
    term: TermConfig | None = None,
) -> list[str]:
    return validate_rooms(RoomConfig(rooms=[*rooms.rooms, room]), courses=courses, term=term)


def validate_student_group(
    group: StudentsGroups,
    ctx: ValidationContext,
    *,
    exclude_code: str | None = None,
) -> list[str]:
    other_groups = [item for item in ctx.sections.students_groups if item.code != exclude_code]
    return validate_sections(SectionsConfig(sections=ctx.sections.sections, students_groups=[*other_groups, group]))


def validate_room_delete(room_id: str, ctx: ValidationContext) -> list[str]:
    referenced_ids = {item for item in collect_course_references(ctx.courses).room_ids if not _is_virtual_room_id(item)}
    if room_id in referenced_ids:
        return [f"Cannot remove room {room_id!r}: still referenced in courses"]
    return []


def validate_student_group_delete(code: str, ctx: ValidationContext) -> list[str]:
    old = SectionsConfig(sections=ctx.sections.sections, students_groups=ctx.sections.students_groups)
    new = SectionsConfig(
        sections=ctx.sections.sections,
        students_groups=[group for group in ctx.sections.students_groups if group.code != code],
    )
    return validate_sections_update(old, new, courses=ctx.courses)


def validate_instructor_delete(instructor_id: str, ctx: ValidationContext) -> list[str]:
    old = ctx.instructors
    new = InstructorConfig(instructors=[item for item in ctx.instructors.instructors if item.id != instructor_id])
    return validate_instructors_update(old, new, courses=ctx.courses)


def validate_resource_update(
    resource: str,
    new_value: TermConfig | SectionsConfig | CoursesConfig | RoomConfig | InstructorConfig,
    old_value: TermConfig | SectionsConfig | CoursesConfig | RoomConfig | InstructorConfig,
    ctx: ValidationContext,
) -> list[str]:
    if resource == "term":
        assert isinstance(new_value, TermConfig)
        return validate_term(new_value)
    if resource == "rooms":
        assert isinstance(new_value, RoomConfig) and isinstance(old_value, RoomConfig)
        return validate_rooms_update(old_value, new_value, courses=ctx.courses, term=ctx.term)
    if resource == "instructors":
        assert isinstance(new_value, InstructorConfig) and isinstance(old_value, InstructorConfig)
        return validate_instructors_update(old_value, new_value, courses=ctx.courses)
    if resource == "sections":
        assert isinstance(new_value, SectionsConfig) and isinstance(old_value, SectionsConfig)
        return validate_sections_update(old_value, new_value, courses=ctx.courses)
    if resource == "courses":
        assert isinstance(new_value, CoursesConfig)
        return validate_courses(new_value, ctx)
    return []
