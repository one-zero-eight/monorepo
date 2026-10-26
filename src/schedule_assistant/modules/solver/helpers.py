import datetime as dtm

from src.schedule_assistant.modules.schedule_config.helpers import expand_groups
from src.schedule_assistant.modules.schedule_config.schemas import CourseConfig, ScheduleConfig


def scheduling_targets(
    component: CourseConfig.Component,
    selector_map: dict[str, set[str]],
) -> list[tuple[list[str], int | None, int]]:
    """Select weekly work without inventing slots for concrete-date series."""
    groups = expand_groups(component.audience, selector_map)
    has_series_windows = any(session.active is not None for session in component.sessions or [])
    if not has_series_windows:
        if component.sessions and all(
            session.dates_pattern and not session.weekly_pattern for session in component.sessions
        ):
            return []
        audiences = [[group] for group in groups] if component.per_group else [groups]
        return [(audience, None, component.per_week or 0) for audience in audiences if audience]
    targets: list[tuple[list[str], int | None, int]] = []
    for index, session in enumerate(component.sessions or []):
        if session.dates_pattern and not session.weekly_pattern:
            continue
        session_groups = expand_groups(session.audience or component.audience, selector_map)
        audiences = [[group] for group in session_groups] if component.per_group else [session_groups]
        slot_count = len(session.weekly_pattern) if session.weekly_pattern is not None else component.per_week or 0
        targets.extend((audience, index, slot_count) for audience in audiences if audience)
    return targets


def resource_weeks(teaching_weeks: tuple[dtm.date, ...] | None) -> tuple[dtm.date | None, ...]:
    """None is an unbounded weekly pattern; an empty phase has no resources."""
    return (None,) if teaching_weeks is None else teaching_weeks


def teaching_days(cfg: ScheduleConfig) -> list[str]:
    configured_days = list(dict.fromkeys(cfg.term.days))
    if not configured_days:
        return []
    start_day = cfg.term.starting_day
    if start_day not in configured_days:
        return [day.value for day in configured_days]
    start_idx = configured_days.index(start_day)
    ordered = configured_days[start_idx:] + configured_days[:start_idx]
    return [day.value for day in ordered]
