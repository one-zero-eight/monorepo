"""Resolve teaching date windows from term + optional per-program semester overrides."""

import datetime as dtm

from src.schedule_assistant.modules.schedule_config.schemas import (
    SectionConfig,
    SectionsConfig,
    TermConfig,
)


def _section_list(source: SectionsConfig | TermConfig | list[SectionConfig]) -> list[SectionConfig]:
    if isinstance(source, list):
        return source
    return list(source.sections)


def build_audience_to_program_code(sections: SectionsConfig | TermConfig | list[SectionConfig]) -> dict[str, str]:
    """Map group codes and @selectors to program.code."""
    mapping: dict[str, str] = {}
    for section in _section_list(sections):
        for program in section.programs:
            mapping[f"@{program.code}"] = program.code
            for group in program.groups:
                mapping[group] = program.code
            for track in program.tracks:
                for group in track.groups:
                    mapping[group] = program.code
                mapping[f"@{program.code}/{track.name}"] = program.code
                mapping[f"@{program.code}/{track.code}"] = program.code
    return mapping


def build_program_semester_by_code(
    sections: SectionsConfig | TermConfig | list[SectionConfig],
) -> dict[str, TermConfig.DateRange]:
    """program.code → semester override (only programs that set semester)."""
    by_code: dict[str, TermConfig.DateRange] = {}
    for section in _section_list(sections):
        for program in section.programs:
            if program.semester is not None:
                by_code[program.code] = program.semester
    return by_code


def program_semester_or_term(
    term: TermConfig,
    program_code: str | None,
    *,
    program_semesters: dict[str, TermConfig.DateRange] | None = None,
) -> TermConfig.DateRange:
    overrides = program_semesters if program_semesters is not None else build_program_semester_by_code(term)
    if program_code and program_code in overrides:
        return overrides[program_code]
    return term.semester


def resolve_audience_semester(
    term: TermConfig,
    audiences: list[str],
    *,
    audience_to_program: dict[str, str] | None = None,
    program_semesters: dict[str, TermConfig.DateRange] | None = None,
    sections: SectionsConfig | None = None,
) -> TermConfig.DateRange | None:
    """Intersection of program windows for session audiences; None if empty."""
    if not audiences:
        return term.semester

    section_source: SectionsConfig | TermConfig = sections if sections is not None else term
    mapping = audience_to_program if audience_to_program is not None else build_audience_to_program_code(section_source)
    overrides = program_semesters if program_semesters is not None else build_program_semester_by_code(section_source)

    windows: list[TermConfig.DateRange] = []
    for audience in audiences:
        token = audience.strip()
        program_code = mapping.get(token)
        windows.append(program_semester_or_term(term, program_code, program_semesters=overrides))

    start = max(window.start_date for window in windows)
    end = min(window.end_date for window in windows)
    if start > end:
        return None
    return TermConfig.DateRange(start_date=start, end_date=end)


def union_semester_window(term: TermConfig, *, sections: SectionsConfig | None = None) -> TermConfig.DateRange:
    """Bounding box of term.semester and all program.semester overrides."""
    start = term.semester.start_date
    end = term.semester.end_date
    for section in _section_list(sections if sections is not None else term):
        for program in section.programs:
            if program.semester is None:
                continue
            start = min(start, program.semester.start_date)
            end = max(end, program.semester.end_date)
    return TermConfig.DateRange(start_date=start, end_date=end)


def meeting_dates_in_window(
    window: TermConfig.DateRange,
    weekday_python: int,
) -> list[dtm.date]:
    dates: list[dtm.date] = []
    current = window.start_date
    while current <= window.end_date:
        if current.weekday() == weekday_python:
            dates.append(current)
        current += dtm.timedelta(days=1)
    return dates
