import datetime as dtm
from collections.abc import Iterable

from src.schedule_assistant.modules.schedule_config.helpers import expand_groups, resolve_selector_map
from src.schedule_assistant.modules.schedule_config.schemas import (
    InstructorConfig,
    InstructorSlotPreferenceLevel,
    ScheduleConfig,
    TermConfig,
)
from src.schedule_assistant.modules.schedule_config.validation import teaching_days_from_term_config
from src.schedule_assistant.weekday import Weekday

DISCOURAGED_BASE_WEIGHT = 1


def instructor_role_multiplier(position: str | None) -> int:
    normalized = (position or "").strip().casefold()
    if normalized in {"professor", "visiting"}:
        return 2
    return 1


def _day_index_by_name(term: TermConfig) -> dict[str, int]:
    ordered = teaching_days_from_term_config(term)
    return {day: index for index, day in enumerate(ordered)}


def teaching_days_from_term(term: TermConfig) -> list[str]:
    return teaching_days_from_term_config(term)


def _slot_index_by_start(term: TermConfig) -> dict[dtm.time, int]:
    return {slot.start_time: index for index, slot in enumerate(term.time_slots)}


def _cell_key(weekday: Weekday | str, start_time: dtm.time, term: TermConfig) -> tuple[int, int] | None:
    day_name = weekday.value if isinstance(weekday, Weekday) else str(weekday).upper()
    day_indices = _day_index_by_name(term)
    slot_indices = _slot_index_by_start(term)
    if day_name not in day_indices:
        return None
    if start_time not in slot_indices:
        return None
    return day_indices[day_name], slot_indices[start_time]


def resolve_preference_grids(
    instructors: Iterable[InstructorConfig.Instructor],
    term: TermConfig,
) -> tuple[dict[str, set[tuple[int, int]]], dict[str, dict[tuple[int, int], int]]]:
    banned: dict[str, set[tuple[int, int]]] = {}
    discouraged: dict[str, dict[tuple[int, int], int]] = {}
    for instructor in instructors:
        for entry in instructor.slot_preferences:
            if entry.level == InstructorSlotPreferenceLevel.NEUTRAL:
                continue
            cell = _cell_key(entry.weekday, entry.start_time, term)
            if cell is None:
                continue
            if entry.level == InstructorSlotPreferenceLevel.BANNED:
                banned.setdefault(instructor.id, set()).add(cell)
            elif entry.level == InstructorSlotPreferenceLevel.DISCOURAGED:
                weight = DISCOURAGED_BASE_WEIGHT * instructor_role_multiplier(instructor.position)
                discouraged.setdefault(instructor.id, {})[cell] = weight
    return banned, discouraged


def resolve_preference_grids_from_config(
    cfg: ScheduleConfig,
) -> tuple[dict[str, set[tuple[int, int]]], dict[str, dict[tuple[int, int], int]]]:
    return resolve_preference_grids(cfg.instructors, cfg.term)


def meeting_instructor_ids(instructor_options: list[list[str]]) -> set[str]:
    out: set[str] = set()
    for option in instructor_options:
        for inst in option:
            if inst:
                out.add(inst)
    return out


def validate_instructor_slot_preferences(
    instructor: InstructorConfig.Instructor,
    term: TermConfig,
    *,
    path_prefix: str = "slot_preferences",
) -> list[str]:
    errors: list[str] = []
    day_indices = _day_index_by_name(term)
    slot_indices = _slot_index_by_start(term)
    seen: set[tuple[str, dtm.time]] = set()
    for index, entry in enumerate(instructor.slot_preferences):
        prefix = f"{path_prefix}[{index}]"
        day_name = entry.weekday.value
        if day_name not in day_indices:
            errors.append(f"{prefix}.weekday {day_name!r} is not in term.days")
        if entry.start_time not in slot_indices:
            errors.append(f"{prefix}.start_time {entry.start_time!r} does not match any term.time_slots start_time")
        key = (day_name, entry.start_time)
        if key in seen:
            errors.append(f"{prefix}: duplicate weekday+start_time ({day_name!r}, {entry.start_time!r})")
        seen.add(key)
        if entry.level == InstructorSlotPreferenceLevel.NEUTRAL:
            errors.append(f"{prefix}.level should be omitted instead of neutral")
    return errors


def _event_day_slot_indices(
    day: str,
    start_time: dtm.time,
    term: TermConfig,
) -> tuple[int, int] | None:
    day_indices = _day_index_by_name(term)
    slot_indices = _slot_index_by_start(term)
    if day not in day_indices or start_time not in slot_indices:
        return None
    return day_indices[day], slot_indices[start_time]


def list_banned_placement_violations(
    *,
    instructors: Iterable[InstructorConfig.Instructor],
    term: TermConfig,
    meetings: Iterable[tuple[str, tuple[str, ...], dtm.time]],
) -> list[str]:
    """Each meeting item is (day, instructor_ids, start_time)."""
    banned, _ = resolve_preference_grids(instructors, term)
    if not banned:
        return []
    instructor_by_id = {inst.id: inst for inst in instructors}
    out: list[str] = []
    for day, instructor_ids, start_time in meetings:
        cell = _event_day_slot_indices(day, start_time, term)
        if cell is None:
            continue
        for inst_id in instructor_ids:
            if inst_id not in banned or cell not in banned[inst_id]:
                continue
            inst = instructor_by_id.get(inst_id)
            label = inst.name_en or inst.name_ru or inst_id if inst else inst_id
            out.append(
                f"instructor {label!r}: meeting on {day} at {start_time.isoformat(timespec='minutes')} uses banned slot"
            )
    return out


def count_discouraged_placement_violations(
    *,
    instructors: Iterable[InstructorConfig.Instructor],
    term: TermConfig,
    meetings: Iterable[tuple[str, tuple[str, ...], dtm.time]],
) -> tuple[int, int, set[str]]:
    """Returns (weighted_total, violation_count, instructors_with_violations)."""
    _, discouraged = resolve_preference_grids(instructors, term)
    if not discouraged:
        return 0, 0, set()
    weighted_total = 0
    violation_count = 0
    instructors_hit: set[str] = set()
    for day, instructor_ids, start_time in meetings:
        cell = _event_day_slot_indices(day, start_time, term)
        if cell is None:
            continue
        for inst_id in instructor_ids:
            weights = discouraged.get(inst_id)
            if not weights:
                continue
            weight = weights.get(cell)
            if weight is None or weight <= 0:
                continue
            weighted_total += weight
            violation_count += 1
            instructors_hit.add(inst_id)
    return weighted_total, violation_count, instructors_hit


def discouraged_opportunities_from_config(cfg: ScheduleConfig) -> int:
    _, discouraged = resolve_preference_grids(cfg.instructors, cfg.term)
    if not discouraged:
        return 0
    selector_map = resolve_selector_map(cfg)
    total = 0
    for course in cfg.courses:
        for comp in course.components:
            if not comp.instructor_pool:
                continue
            groups = expand_groups(comp.student_groups, selector_map)
            if not groups:
                continue
            audiences = [[group] for group in groups] if comp.per_group else [groups]
            instructor_ids: set[str] = set()
            for pool_entry in comp.instructor_pool:
                if isinstance(pool_entry, list):
                    instructor_ids.update(pool_entry)
                else:
                    instructor_ids.add(pool_entry)
            for _audience in audiences:
                for _week in range(comp.per_week or 0):
                    for inst_id in instructor_ids:
                        total += sum(discouraged.get(inst_id, {}).values())
    return total


def meeting_day_slot_cell(
    day: str,
    start_time: dtm.time,
    term: TermConfig,
) -> tuple[int, int] | None:
    return _event_day_slot_indices(day, start_time, term)


def discouraged_opportunities_upper_bound(
    meetings: Iterable[tuple[int, set[str]]],
    discouraged: dict[str, dict[tuple[int, int], int]],
) -> int:
    total = 0
    for _m_idx, instructor_ids in meetings:
        for inst_id in instructor_ids:
            total += sum(discouraged.get(inst_id, {}).values())
    return total
