from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.meetings import (
    _group_codes_for_session,
    build_token_to_section_kind,
    source_kind_from_audiences,
)
from src.schedule_assistant.modules.issues.schemas import IssueTypeEnum, PerWeekIssue
from src.schedule_assistant.modules.schedule_config.schemas import ComponentSessionSeries, CoursesConfig, SectionsConfig
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens


def _weekly_slot_count_for_audience(
    sessions: list[ComponentSessionSeries],
    *,
    component_groups: list[str],
    audience: tuple[str, ...],
    selector_map: dict[str, set[str]],
) -> int:
    count = 0
    for session in sessions:
        session_audience = _group_codes_for_session(component_groups, session, selector_map)
        if session_audience != audience:
            continue
        if session.weekly_pattern:
            count += len(session.weekly_pattern)
    return count


def per_week_issues_from_schedule_config(courses: CoursesConfig, sections: SectionsConfig) -> list[PerWeekIssue]:
    selector_map = build_selector_map(sections)
    token_to_kind = build_token_to_section_kind(sections)
    issues: list[PerWeekIssue] = []

    for course in courses.courses:
        for component in course.components:
            if component.per_week is None:
                continue

            expanded_groups = expand_group_tokens(component.student_groups, selector_map)
            if not expanded_groups:
                continue

            audiences = (
                [(group,) for group in sorted(expanded_groups)]
                if component.per_group
                else [tuple(sorted(expanded_groups))]
            )
            sessions = component.sessions or []

            for audience in audiences:
                actual = _weekly_slot_count_for_audience(
                    sessions,
                    component_groups=component.student_groups,
                    audience=audience,
                    selector_map=selector_map,
                )
                if actual == component.per_week:
                    continue

                issue = PerWeekIssue(
                    issue_type=IssueTypeEnum.PER_WEEK,
                    course_name=course.name,
                    component_tag=component.tag,
                    source_kind=source_kind_from_audiences(
                        list(audience) or component.student_groups,
                        token_to_kind,
                    ),
                    student_groups=audience,
                    expected_per_week=component.per_week,
                    actual_per_week=actual,
                )
                attach_issue_text(issue)
                issues.append(issue)

    return issues
