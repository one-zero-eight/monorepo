import datetime as dtm
from collections import Counter

from src.schedule_assistant.modules.issues.issue_text import attach_issue_text
from src.schedule_assistant.modules.issues.meetings import _group_codes_for_session
from src.schedule_assistant.modules.issues.schemas import IssueTypeEnum, PerWeekIssue
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CoursesConfig,
    SectionsConfig,
    TermConfig,
)
from src.schedule_assistant.modules.schedule_config.semester_windows import resolve_session_window
from src.schedule_assistant.modules.schedule_config.validation import build_selector_map, expand_group_tokens
from src.schedule_assistant.modules.schedule_config.weekly_dates import active_weekly_dates
from src.schedule_assistant.weekday import week_start_for_date


def _weekly_counts_for_audience(
    sessions: list[ComponentSessionSeries],
    *,
    component_groups: list[str],
    audience: tuple[str, ...],
    selector_map: dict[str, set[str]],
    per_group: bool,
    term: TermConfig | None,
    sections: SectionsConfig,
) -> set[int]:
    audience_set = set(audience)
    weekly_counts: Counter[dtm.date | None] = Counter()
    for session in sessions:
        session_audience = set(_group_codes_for_session(component_groups, session, selector_map))
        if per_group:
            if not audience_set or not audience_set <= session_audience:
                continue
        elif session_audience != audience_set:
            continue
        if term is None:
            weekly_counts[None] += len(session.weekly_pattern or [])
            continue
        window = resolve_session_window(
            term, list(session.audience or component_groups), session.active, sections=sections
        )
        if window is None:
            continue
        for slot in session.weekly_pattern or []:
            if term.days and slot.weekday not in term.days:
                continue
            # per_week describes configured slots, so alternation and one-off edits
            # do not change their count. Only slots with a source in the same
            # teaching week are concurrent; inactive gaps are not teaching weeks.
            for source_date in active_weekly_dates(window, slot.weekday, term.starting_day):
                weekly_counts[week_start_for_date(source_date, term.starting_day)] += 1
    return set(weekly_counts.values()) or {0}


def per_week_issues_from_schedule_config(
    courses: CoursesConfig,
    sections: SectionsConfig,
    term: TermConfig | None = None,
) -> list[PerWeekIssue]:
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
            for audience in audiences:
                actual_counts = _weekly_counts_for_audience(
                    component.sessions or [],
                    component_groups=component.audience,
                    audience=audience,
                    selector_map=selector_map,
                    per_group=component.per_group,
                    term=term,
                    sections=sections,
                )
                for actual in sorted(actual_counts):
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
