import datetime as dtm
from collections import defaultdict

from src.logging_ import logger
from src.schedule_assistant.electives.cell_to_event import ElectiveEvent
from src.schedule_assistant.electives.config import ElectivesParserConfig
from src.schedule_assistant.electives.parser import ElectiveParser
from src.schedule_assistant.utils import fetch_xlsx_spreadsheet, get_sheet_gids

from .core_courses_adapter import _as_audience_list
from .schemas import ElectiveLessonOccurrence, GroupedElective, Lesson


async def get_grouped_elective_lessons(parser_config: ElectivesParserConfig) -> list[GroupedElective]:
    flat_lessons = await _collect_elective_lessons(parser_config)
    grouped = group_elective_lessons(flat_lessons)
    logger.info(f"Grouped elective lessons: {len(flat_lessons)} -> {len(grouped)}")
    return grouped


async def _collect_elective_lessons(parser_config: ElectivesParserConfig) -> list[Lesson]:
    parser = ElectiveParser()
    xlsx_file = await fetch_xlsx_spreadsheet(spreadsheet_id=parser_config.spreadsheet_id)
    original_target_sheet_names = [target.sheet_name for target in parser_config.targets]
    sheet_gids = await get_sheet_gids(parser_config.spreadsheet_id)
    pipeline_result = list(
        parser.pipeline(
            xlsx_file, original_target_sheet_names, parser_config.electives, sheet_gids, parser_config.spreadsheet_id
        )
    )

    all_lessons: list[Lesson] = []
    for target, separations_list in zip(parser_config.targets, pipeline_result):
        for separation in separations_list:
            for event in separation.events:
                lesson = _event_to_lesson(event)
                if lesson:
                    all_lessons.append(lesson)

        logger.info(
            f"For {target.sheet_name} found {len([s for s in separations_list for _ in s.events])} elective events"
        )

    all_lessons.sort(key=_elective_lesson_sort_key)
    return all_lessons


def _normalize_group_name(group_name: str | tuple[str, ...] | None) -> tuple[str, ...]:
    if group_name is None:
        return ()
    if isinstance(group_name, str):
        return (group_name,)
    return group_name


def _elective_audience(lesson: Lesson) -> list[str]:
    groups = _as_audience_list(lesson.group_name)
    alias = (lesson.course_name or "").strip()
    if alias and groups:
        return [alias, *groups]
    if groups:
        return groups
    if alias:
        return [alias]
    return []


def _elective_lesson_identity_key(lesson: Lesson) -> tuple:
    return (
        lesson.lesson_name,
        lesson.lesson_class_type,
        lesson.teacher,
        tuple(_elective_audience(lesson)),
        lesson.spreadsheet_id,
        lesson.google_sheet_gid,
        lesson.google_sheet_name,
    )


def _elective_lesson_sort_key(lesson: Lesson) -> tuple:
    group = _normalize_group_name(lesson.group_name)
    first_date = lesson.date_on[0] if lesson.date_on else dtm.date.min
    return (lesson.course_name or "", group, first_date, lesson.start_time)


def _grouped_lesson_sort_key(lesson: GroupedElective) -> tuple:
    group = tuple(lesson.audience)
    first_occurrence = lesson.occurrences[0] if lesson.occurrences else None
    first_date = first_occurrence.date if first_occurrence else dtm.date.min
    start_time = first_occurrence.start_time if first_occurrence else dtm.time()
    return (lesson.subject, group, first_date, start_time)


def _lesson_to_occurrence(lesson: Lesson) -> ElectiveLessonOccurrence | None:
    if not lesson.date_on:
        return None
    return ElectiveLessonOccurrence(
        start_time=lesson.start_time,
        end_time=lesson.end_time,
        date=lesson.date_on[0],
        room=lesson.room,
        a1_range=lesson.a1_range,
    )


def group_elective_lessons(lessons: list[Lesson]) -> list[GroupedElective]:
    """Group flat elective lessons by course/teacher; each date/time/room is one occurrence."""
    by_identity: dict[tuple, list[Lesson]] = defaultdict(list)
    for lesson in lessons:
        by_identity[_elective_lesson_identity_key(lesson)].append(lesson)

    grouped: list[GroupedElective] = []
    for identity_lessons in by_identity.values():
        occurrences_by_key: dict[tuple, ElectiveLessonOccurrence] = {}
        for lesson in identity_lessons:
            occurrence = _lesson_to_occurrence(lesson)
            if occurrence is None:
                continue
            key = (
                occurrence.start_time,
                occurrence.end_time,
                occurrence.date,
                occurrence.room,
                occurrence.a1_range,
            )
            occurrences_by_key[key] = occurrence

        occurrences = sorted(
            occurrences_by_key.values(),
            key=lambda occurrence: (occurrence.date, occurrence.start_time),
        )
        template = identity_lessons[0]
        grouped.append(
            GroupedElective(
                subject=template.lesson_name,
                alias=(template.course_name or "").strip() or None,
                instructor=template.teacher,
                audience=_elective_audience(template),
                spreadsheet_id=template.spreadsheet_id,
                google_sheet_gid=template.google_sheet_gid,
                google_sheet_name=template.google_sheet_name,
                occurrences=occurrences,
            )
        )

    grouped.sort(key=_grouped_lesson_sort_key)
    return grouped


def _audience_to_course_and_group(audience: list[str]) -> tuple[str | None, str | tuple[str, ...] | None]:
    if not audience:
        return None, None
    if len(audience) == 1:
        token = audience[0]
        if len(token) == 2 and token[0] == "G" and token[1].isdigit():
            return None, token
        return token, None
    return audience[0], tuple(audience)


def grouped_elective_to_json(elective: GroupedElective) -> dict:
    return elective.model_dump(mode="json")


def expand_grouped_elective_lessons(grouped: list[GroupedElective]) -> list[Lesson]:
    """Expand grouped elective lessons back to flat lessons for collision checks."""
    flat: list[Lesson] = []
    for grouped_lesson in grouped:
        course_name, group_name = _audience_to_course_and_group(grouped_lesson.audience)
        for occurrence in grouped_lesson.occurrences:
            flat.append(
                Lesson(
                    lesson_name=grouped_lesson.subject,
                    lesson_class_type=None,
                    weekday=None,
                    start_time=occurrence.start_time,
                    end_time=occurrence.end_time,
                    course_name=course_name,
                    group_name=group_name,
                    teacher=grouped_lesson.instructor,
                    room=occurrence.room,
                    source_type="elective",
                    date_on=[occurrence.date],
                    date_except=None,
                    students_number=None,
                    spreadsheet_id=grouped_lesson.spreadsheet_id,
                    google_sheet_gid=grouped_lesson.google_sheet_gid,
                    google_sheet_name=grouped_lesson.google_sheet_name,
                    a1_range=occurrence.a1_range,
                )
            )
    flat.sort(key=_elective_lesson_sort_key)
    return flat


def _event_to_lesson(event: ElectiveEvent) -> Lesson | None:
    """
    Convert ElectiveEvent to Lesson
    """
    start_time = event.start.time()
    end_time = event.end.time()

    lesson_name = event.elective.name or event.elective.alias
    course_name = event.elective.alias
    teacher = event.elective.instructor

    return Lesson(
        lesson_name=lesson_name,
        lesson_class_type=event.class_type,
        weekday=None,
        start_time=start_time,
        end_time=end_time,
        course_name=course_name,
        group_name=event.group,
        teacher=teacher,
        room=event.location,
        source_type="elective",
        date_on=[event.start.date()] if event.start else None,
        date_except=None,
        students_number=None,
        spreadsheet_id=event.spreadsheet_id,
        google_sheet_gid=event.google_sheet_gid,
        google_sheet_name=event.google_sheet_name,
        a1_range=event.a1,
    )
