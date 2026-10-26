import datetime as dtm
from copy import deepcopy

import icalendar
import pytest
from httpx import AsyncClient
from pydantic import ValidationError

from src.schedule_assistant.modules.bookings.match import iter_payload_occurrences
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.issues.meetings import unplaced_issues_from_schedule_config
from src.schedule_assistant.modules.issues.per_week import per_week_issues_from_schedule_config
from src.schedule_assistant.modules.issues.placement import iter_concrete_dates, meetings_overlap
from src.schedule_assistant.modules.issues.schemas import OccurrencePlacement, ScheduledMeeting
from src.schedule_assistant.modules.schedule.domain import meetings_from_schedule_config
from src.schedule_assistant.modules.schedule.export_xlsx import expand_meetings
from src.schedule_assistant.modules.schedule.ics import render_calendar
from src.schedule_assistant.modules.schedule_config.helpers import resolve_selector_map
from src.schedule_assistant.modules.schedule_config.instructor_meetings import count_meetings_by_instructor
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CoursesConfig,
    InstructorConfig,
    RoomConfig,
    ScheduleConfig,
    SectionsConfig,
    SessionOccurrence,
    TermConfig,
    WeeklyPatternSlotEdit,
)
from src.schedule_assistant.modules.schedule_config.validation import ValidationContext, validate_courses, validate_term
from src.schedule_assistant.modules.schedule_config.weekly_pattern_canonicalization import canonicalize_courses
from src.schedule_assistant.modules.solver.helpers import resource_weeks, scheduling_targets
from src.schedule_assistant.weekday import Weekday


def _range(start: str, end: str) -> TermConfig.DateRange:
    return TermConfig.DateRange(start_date=dtm.date.fromisoformat(start), end_date=dtm.date.fromisoformat(end))


def _config() -> ScheduleConfig:
    return ScheduleConfig.model_validate(
        {
            "term": {
                "name": "Fall",
                "semester": {"start_date": "2026-09-01", "end_date": "2026-10-31"},
                "blocks": [
                    {"id": "first", "name": "First", "start_date": "2026-09-01", "end_date": "2026-09-30"},
                    {"id": "second", "name": "Second", "start_date": "2026-10-01", "end_date": "2026-10-31"},
                ],
                "sections": [
                    {"code": "core", "name": "Core", "programs": [{"code": "BS", "name": "BS", "groups": ["G1"]}]}
                ],
            },
            "rooms": [{"id": "108", "name": "108", "capacity": 30}],
            "instructors": [{"id": "teacher"}, {"id": "other"}],
            "students_groups": [{"code": "G1"}],
            "courses": [
                {
                    "name": "Algebra",
                    "section_code": "core",
                    "blocks": ["first"],
                    "components": [
                        {
                            "tag": "lec",
                            "audience": ["G1"],
                            "per_week": 1,
                            "instructor_pool": ["teacher"],
                            "sessions": [
                                {
                                    "audience": ["G1"],
                                    "active": {"start_date": "2026-09-08", "end_date": "2026-09-29"},
                                    "weekly_pattern": [
                                        {
                                            "weekday": "TUESDAY",
                                            "start_time": "09:00",
                                            "end_time": "10:30",
                                            "room": "108",
                                            "instructor": "teacher",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                }
            ],
        }
    )


def _parts(config: ScheduleConfig) -> tuple[CoursesConfig, SectionsConfig]:
    return CoursesConfig(courses=config.courses), SectionsConfig(
        sections=config.term.sections, students_groups=config.students_groups
    )


def _sessions(config: ScheduleConfig) -> list[ComponentSessionSeries]:
    sessions = config.courses[0].components[0].sessions
    assert sessions
    return sessions


def _occurrence_dates(meetings: list[ScheduledMeeting]) -> list[dtm.date]:
    dates = []
    for meeting in meetings:
        assert isinstance(meeting.placement, OccurrencePlacement)
        dates.append(meeting.placement.date)
    return dates


def _errors(config: ScheduleConfig) -> list[str]:
    courses, sections = _parts(config)
    return validate_courses(
        courses,
        ValidationContext(
            term=config.term,
            courses=courses,
            sections=sections,
            rooms=RoomConfig(rooms=config.rooms),
            instructors=InstructorConfig(instructors=config.instructors),
        ),
    )


def test_schema_defaults_and_required_block_fields() -> None:
    assert ComponentSessionSeries().active is None
    term = TermConfig(name="Fall", semester=_range("2026-09-01", "2026-10-31"))
    assert term.blocks == []
    assert _config().courses[0].model_copy(update={"blocks": None}).blocks is None
    with pytest.raises(ValidationError):
        TermConfig.model_validate({"name": "Fall", "semester": term.semester.model_dump(), "blocks": [{"id": "first"}]})


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("id", "", "id must not be empty"),
        ("name", "  ", "name must not be empty"),
        ("id", "second", "is duplicated"),
        ("start_date", dtm.date(2026, 8, 31), "inside term.semester"),
        ("end_date", dtm.date(2026, 8, 31), "on or before"),
        ("end_date", dtm.date(2026, 10, 1), "overlaps"),
    ],
)
def test_block_validation(field, value, message) -> None:
    config = _config()
    setattr(config.term.blocks[0], field, value)
    assert any(message in error for error in validate_term(config.term))


@pytest.mark.parametrize("blocks", [[], ["first", "first"], ["missing"], [""]])
def test_course_block_references_are_validated(blocks) -> None:
    config = _config()
    config.courses[0].blocks = blocks
    assert any(".blocks" in error for error in _errors(config))


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        ("2026-09-29", "2026-09-08", "on or before"),
        ("2026-08-31", "2026-09-29", "inside term.semester"),
        ("2026-09-09", "2026-09-09", "no source dates"),
    ],
)
def test_active_window_validation(start, end, message) -> None:
    config = _config()
    _sessions(config)[0].active = _range(start, end)
    assert any(message in error for error in _errors(config))


@pytest.mark.parametrize(
    "change",
    [
        {"dates_pattern": [{"date": "2026-09-30", "start_time": "09:00", "end_time": "10:30"}]},
        {
            "weekly_pattern": [
                {
                    "weekday": "TUESDAY",
                    "start_time": "09:00",
                    "end_time": "10:30",
                    "edits": [{"select_week": "2026-09-01", "cancel": True}],
                }
            ]
        },
        {
            "weekly_pattern": [
                {
                    "weekday": "TUESDAY",
                    "start_time": "09:00",
                    "end_time": "10:30",
                    "edits": [{"select_week": "2026-09-08", "date": "2026-09-30"}],
                }
            ]
        },
    ],
)
def test_occurrences_and_edit_sources_and_destinations_must_fit_active(change) -> None:
    config = _config()
    session = _sessions(config)[0]
    _sessions(config)[0] = ComponentSessionSeries.model_validate(session.model_dump() | change)
    assert any("effective session window" in error for error in _errors(config))


def test_partial_first_week_edit_uses_source_date_not_week_anchor() -> None:
    config = _config()
    session = _sessions(config)[0]
    session.active = _range("2026-09-01", "2026-09-01")
    assert session.weekly_pattern
    session.weekly_pattern[0].edits = [WeeklyPatternSlotEdit(select_week=dtm.date(2026, 8, 31), instructor="other")]
    assert not _errors(config)
    assert count_meetings_by_instructor(config.courses, config.term, ["other"]) == {"other": 1}


def test_active_intersects_audience_and_null_preserves_program_override() -> None:
    config = _config()
    config.term.sections[0].programs[0].semester = _range("2026-08-25", "2026-09-22")
    courses, sections = _parts(config)
    meetings = meetings_from_schedule_config(courses, sections, config.term)
    assert [date.isoformat() for date in _occurrence_dates(meetings)] == ["2026-09-08", "2026-09-15", "2026-09-22"]
    _sessions(config)[0].active = None
    meetings = meetings_from_schedule_config(courses, sections, config.term)
    assert _occurrence_dates(meetings)[0] == dtm.date(2026, 8, 25)
    assert len(meetings) == 5
    _sessions(config)[0].active = _range("2026-10-01", "2026-10-31")
    assert any("empty intersection" in error for error in _errors(config))
    assert meetings_from_schedule_config(courses, sections, config.term) == []
    assert len(unplaced_issues_from_schedule_config(courses, sections, config.term)) == 1


def test_expansion_booking_ics_export_counts_share_active_alternation_and_edits() -> None:
    config = _config()
    session = _sessions(config)[0]
    session.active = _range("2026-09-08", "2026-10-20")
    assert session.weekly_pattern
    session.weekly_pattern[0] = session.weekly_pattern[0].model_validate(
        session.weekly_pattern[0].model_dump()
        | {
            "alternation": {"anchor_week": "2026-09-01"},
            "edits": [
                {"select_week": "2026-09-15", "cancel": True},
                {"select_week": "2026-09-29", "date": "2026-09-30", "instructor": "other"},
                {"select_week": "2026-09-08", "date": "2026-09-09"},
            ],
        }
    )
    assert not _errors(config)
    courses, sections = _parts(config)
    expected = [dtm.date(2026, 9, 30), dtm.date(2026, 10, 13)]
    concrete = meetings_from_schedule_config(courses, sections, config.term)
    assert _occurrence_dates(concrete) == expected
    assert [meeting.date for meeting in expand_meetings(config)] == expected
    slots = build_bookable_slots(courses, sections, config.term, {"108"})
    assert sorted(start.date() for slot in slots for start, _ in iter_payload_occurrences(slot.payload)) == expected
    assert count_meetings_by_instructor(config.courses, config.term, ["teacher", "other"]) == {"teacher": 1, "other": 1}
    patterns = meetings_from_schedule_config(courses, sections, config.term, expand_weekly=False)
    assert list(iter_concrete_dates(patterns[0], start_date=expected[0], end_date=expected[0])) == expected[:1]
    calendar = icalendar.Calendar.from_ical(render_calendar("Blocks", [("group", meeting) for meeting in patterns]))
    events = calendar.walk("VEVENT")
    base = next(event for event in events if "RRULE" in event)
    assert base.decoded("DTSTART").date() == dtm.date(2026, 9, 15)
    rule = base["RRULE"]
    assert isinstance(rule, icalendar.vRecur)
    assert rule["INTERVAL"] == [2]
    assert rule["UNTIL"][0].astimezone(dtm.timezone(dtm.timedelta(hours=3))).date() == dtm.date(2026, 10, 20)
    assert len(events) == 2


def test_explicit_occurrences_remain_visible_but_invalid_dates_cannot_be_booked() -> None:
    config = _config()
    session = _sessions(config)[0]
    session.weekly_pattern = None
    session.dates_pattern = [
        SessionOccurrence(
            date=dtm.date(2026, 9, day),
            start_time=dtm.time(9),
            end_time=dtm.time(10, 30),
            room="108",
            instructor="teacher",
        )
        for day in [1, 8, 29, 30]
    ]
    courses, sections = _parts(config)
    expected = [dtm.date(2026, 9, 8), dtm.date(2026, 9, 29)]
    assert _occurrence_dates(meetings_from_schedule_config(courses, sections, config.term)) == [
        occurrence.date for occurrence in session.dates_pattern
    ]
    assert any("outside the effective session window" in error for error in _errors(config))
    assert [meeting.date for meeting in expand_meetings(config)] == expected
    assert count_meetings_by_instructor(config.courses, config.term, ["teacher"]) == {"teacher": 2}
    slots = build_bookable_slots(courses, sections, config.term, {"108"})
    assert [start.date() for slot in slots for start, _ in iter_payload_occurrences(slot.payload)] == expected
    session.dates_pattern = session.dates_pattern[:1]
    assert len(unplaced_issues_from_schedule_config(courses, sections, config.term)) == 1


def test_split_series_concurrency_counts_and_metadata_do_not_restrict_dates() -> None:
    config = _config()
    first = _sessions(config)[0]
    first.active = _range("2026-09-01", "2026-09-30")
    second = first.model_copy(deep=True, update={"active": _range("2026-10-01", "2026-10-31")})
    _sessions(config).append(second)
    courses, sections = _parts(config)
    assert not per_week_issues_from_schedule_config(courses, sections, config.term)
    patterns = meetings_from_schedule_config(courses, sections, config.term, expand_weekly=False)
    assert not meetings_overlap(*patterns)
    assert max(meeting.date for meeting in expand_meetings(config)) == dtm.date(2026, 10, 27)
    # Disjoint date ranges can still contain slots in the same teaching week.
    second.active = _range("2026-09-30", "2026-10-31")
    assert second.weekly_pattern
    second.weekly_pattern[0].weekday = Weekday.FRIDAY
    issues = per_week_issues_from_schedule_config(courses, sections, config.term)
    assert [issue.actual_per_week for issue in issues] == [2]
    # Gaps between teaching blocks must not count as zero weekly slots.
    second.active = _range("2026-10-15", "2026-10-31")
    assert not per_week_issues_from_schedule_config(courses, sections, config.term)


@pytest.mark.parametrize("per_group", [False, True])
def test_solver_targets_expand_selectors_and_split_shared_active_audiences(per_group: bool) -> None:
    config = _config()
    config.term.sections[0].programs[0].groups.append("G2")
    component = config.courses[0].components[0]
    component.audience = ["@BS"]
    component.per_group = per_group
    _sessions(config)[0].audience = ["@BS"]
    targets = scheduling_targets(component, resolve_selector_map(config))
    assert targets == ([(["G1"], 0, 1), (["G2"], 0, 1)] if per_group else [(["G1", "G2"], 0, 1)])


@pytest.mark.parametrize("active", [None, _range("2026-09-08", "2026-09-29")])
@pytest.mark.parametrize("weekly_pattern", [None, []])
def test_dates_only_solver_targets_never_invent_weekly_slots(active, weekly_pattern) -> None:
    config = _config()
    session = _sessions(config)[0]
    session.active = active
    session.weekly_pattern = weekly_pattern
    session.dates_pattern = [
        SessionOccurrence(date=dtm.date(2026, 9, 8), start_time=dtm.time(9), end_time=dtm.time(10, 30))
    ]
    assert scheduling_targets(config.courses[0].components[0], resolve_selector_map(config)) == []


def test_empty_solver_phase_has_no_collision_resources() -> None:
    assert resource_weeks(()) == ()
    assert resource_weeks(None) == (None,)
    assert resource_weeks((dtm.date(2026, 9, 7),)) == (dtm.date(2026, 9, 7),)


def test_per_week_contract_counts_configured_slots_despite_alternation_and_cancellation() -> None:
    config = _config()
    session = _sessions(config)[0]
    assert session.weekly_pattern
    session.weekly_pattern[0] = session.weekly_pattern[0].model_validate(
        session.weekly_pattern[0].model_dump()
        | {
            "alternation": {"anchor_week": "2026-09-08"},
            "edits": [{"select_week": "2026-09-08", "cancel": True}],
        }
    )
    courses, sections = _parts(config)
    assert not per_week_issues_from_schedule_config(courses, sections, config.term)
    assert count_meetings_by_instructor(config.courses, config.term, ["teacher"]) == {"teacher": 1}


def test_canonicalization_uses_active_without_changing_other_blocks() -> None:
    config = _config()
    first = _sessions(config)[0]
    first.active = _range("2026-09-01", "2026-09-15")
    assert first.weekly_pattern
    first.weekly_pattern[0].edits = [
        WeeklyPatternSlotEdit(select_week=dtm.date(2026, 9, day), instructor="other") for day in [1, 8, 15]
    ]
    second = first.model_copy(deep=True, update={"active": _range("2026-10-01", "2026-10-31")})
    assert second.weekly_pattern
    second.weekly_pattern[0].edits = None
    _sessions(config).append(second)
    before = expand_meetings(config)
    config.courses, _ = canonicalize_courses(config.courses, config.term)
    assert expand_meetings(config) == before
    first, second = _sessions(config)
    assert first.weekly_pattern
    assert second.weekly_pattern
    assert first.weekly_pattern[0].instructor == "other"
    assert first.weekly_pattern[0].edits is None
    assert second.weekly_pattern[0].instructor == "teacher"


@pytest.mark.asyncio
async def test_crud_persists_blocks_and_windows_and_public_contract(
    authenticated_client: AsyncClient,
    schedule_config_repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    config = _config()
    response = await authenticated_client.put("/schedule-config/", json=config.model_dump(mode="json"))
    assert response.status_code == 200, response.text
    original_revision = response.headers["etag"]
    saved = (await authenticated_client.get("/schedule-config/")).json()
    assert saved["term"]["blocks"] == config.term.model_dump(mode="json")["blocks"]
    assert saved["courses"][0]["blocks"] == ["first"]
    active = saved["courses"][0]["components"][0]["sessions"][0]["active"]
    public = (await authenticated_client.get("/timetable")).json()
    assert public["term"]["blocks"] == saved["term"]["blocks"]
    assert public["courses"][0]["blocks"] == ["first"]
    assert public["courses"][0]["components"][0]["sessions"][0]["active"] == active
    schema = (await authenticated_client.get("/openapi.json")).json()["components"]["schemas"]
    assert "blocks" in schema["TermConfig"]["properties"]
    assert "active" in schema["ComponentSessionSeries"]["properties"]
    assert "TermBlock" in schema
    # Renaming and moving a preset never rewrites a stored series window.
    term = saved["term"]
    term["blocks"][0]["name"] = "Renamed"
    term["blocks"][0]["end_date"] = "2026-09-20"
    updated = await authenticated_client.put("/schedule-config/term", json=term)
    assert updated.status_code == 200, updated.text
    assert updated.headers["etag"] != original_revision
    course = (await authenticated_client.get("/schedule-config/courses/Algebra")).json()
    assert course["components"][0]["sessions"][0]["active"] == active
    term["blocks"] = term["blocks"][1:]
    rejected = await authenticated_client.put("/schedule-config/term", json=term)
    assert rejected.status_code == 422
    course["blocks"] = None
    course["components"][0]["sessions"][0]["active"] = None
    updated = await authenticated_client.put("/schedule-config/courses/Algebra", json=course)
    assert updated.status_code == 200, updated.text
    assert updated.json()["blocks"] is None
    assert (await authenticated_client.put("/schedule-config/term", json=term)).status_code == 200
    assert (await authenticated_client.delete("/schedule-config/courses/Algebra")).status_code == 204
    assert (await authenticated_client.post("/schedule-config/courses", json=course)).status_code == 201
    assert schedule_config_repo.get_assembled().courses[0].blocks is None


@pytest.mark.asyncio
async def test_term_and_section_updates_cannot_invalidate_active_windows(
    authenticated_client: AsyncClient,
    schedule_config_repo,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    config = _config()
    assert (await authenticated_client.put("/schedule-config/", json=config.model_dump(mode="json"))).status_code == 200
    sections = deepcopy(config.term.model_dump(mode="json")["sections"])
    sections[0]["programs"][0]["semester"] = {"start_date": "2026-10-01", "end_date": "2026-10-31"}
    response = await authenticated_client.put("/schedule-config/", json={"term": {"sections": sections}})
    assert response.status_code == 422
    assert schedule_config_repo.get_term().sections[0].programs[0].semester is None
    response = await authenticated_client.put(
        "/schedule-config/", json={"courses": [config.courses[0].model_dump(mode="json") | {"blocks": ["unknown"]}]}
    )
    assert response.status_code == 422
