from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.meetings import _group_codes_for_session
from src.schedule_assistant.modules.issues.schemas import IssueTypeEnum, PerWeekIssue
from src.schedule_assistant.modules.schedule_config.schemas import ComponentSessionSeries, CoursesConfig, SectionsConfig
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens


def _weekly_slot_count_for_audience(
    sessions: list[ComponentSessionSeries],
    *,
    component_groups: list[str],
    audience: tuple[str, ...],
    selector_map: dict[str, set[str]],
    per_group: bool,
) -> int:
    audience_set = set(audience)
    count = 0
    for session in sessions:
        session_audience = set(_group_codes_for_session(component_groups, session, selector_map))
        if per_group:
            if not audience_set or not audience_set <= session_audience:
                continue
        elif session_audience != audience_set:
            continue
        if session.weekly_pattern:
            count += len(session.weekly_pattern)
    return count


def per_week_issues_from_schedule_config(courses: CoursesConfig, sections: SectionsConfig) -> list[PerWeekIssue]:
    selector_map = build_selector_map(sections)
    issues: list[PerWeekIssue] = []

    for course in courses.courses:
        for component in course.components:
            if component.per_week is None:
                continue

            expanded_groups = expand_group_tokens(component.audience, selector_map)
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
                    component_groups=component.audience,
                    audience=audience,
                    selector_map=selector_map,
                    per_group=component.per_group,
                )
                if actual == component.per_week:
                    continue

                issue = PerWeekIssue(
                    issue_type=IssueTypeEnum.PER_WEEK,
                    course_name=course.name,
                    component_tag=component.tag,
                    student_groups=audience,
                    expected_per_week=component.per_week,
                    actual_per_week=actual,
                )
                attach_issue_text(issue)
                issues.append(issue)

    return issues
