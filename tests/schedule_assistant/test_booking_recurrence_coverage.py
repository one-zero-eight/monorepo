import datetime as dtm

import pytest

from src.schedule_assistant.modules.bookings.client import BookingDTO
from src.schedule_assistant.modules.bookings.match import (
    booking_coverage,
    detect_payload_conflicts,
    find_extra_auto_bookings,
    find_matching_auto_booking,
    iter_booking_occurrences,
    iter_payload_occurrences,
)
from src.schedule_assistant.modules.bookings.review import (
    build_review_index,
    collect_booking_payloads,
    split_payloads_around_conflicts,
)
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.schedule_config.schemas import CoursesConfig, SectionsConfig, TermConfig


def payload() -> dict:
    return {
        "room_id": "209",
        "title": "Algebra (lab, B26-MFAI-03)",
        "start": "2026-09-11T12:40:00+03:00",
        "end": "2026-09-11T14:10:00+03:00",
        "categories": ["core", "B26-MFAI-03", "Algebra"],
        "recurrence": {"weekday": "friday", "start_date": "2026-09-11", "until_date": "2026-09-25"},
    }


def booking(**changes) -> dict:
    data = {
        **payload(),
        "title": "Auto: Algebra (lab, B26-MFAI-03)",
        "uid": "series-1",
        "organizer_mailbox": "organizer@example.com",
        "outlook_booking_id": "master-1",
        "room_response": "Tentative",
        "room_presence": "present",
        "recurrence_complete": True,
    }
    data.update(changes)
    return data


def test_single_occurrence_does_not_cover_whole_series() -> None:
    own = booking(recurrence=None)
    result = booking_coverage(payload(), [own])
    assert {start.date().isoformat() for start, _ in result.covered} == {"2026-09-11"}
    assert {start.date().isoformat() for start, _ in result.missing} == {"2026-09-18", "2026-09-25"}
    assert find_matching_auto_booking(payload(), [own]) is None


def test_interval_start_and_exceptions_change_exact_coverage() -> None:
    own = booking(recurrence={**payload()["recurrence"], "interval": 2})
    assert {start.day for start, _ in booking_coverage(payload(), [own]).missing} == {18}
    own = booking(
        deleted_occurrences=["2026-09-18T12:40:00+03:00"],
        modified_occurrences=[
            {
                "original_start": "2026-09-25T12:40:00+03:00",
                "start": "2026-09-26T14:20:00+03:00",
                "end": "2026-09-26T15:50:00+03:00",
            }
        ],
    )
    assert {start.day for start, _ in booking_coverage(payload(), [own]).missing} == {18, 25}
    assert {start.day for start, _ in iter_booking_occurrences(own)} == {11, 26}
    late = booking(recurrence={**payload()["recurrence"], "start_date": "2026-09-18"})
    assert find_matching_auto_booking(payload(), [late]) is None


def test_xml_interval_and_incomplete_recurrence_are_not_assumed_weekly() -> None:
    own = booking(
        recurrence=(
            "<t:WeeklyRecurrence><t:Interval>2</t:Interval><t:DaysOfWeek>Friday</t:DaysOfWeek></t:WeeklyRecurrence>"
            "<t:StartDate>2026-09-11</t:StartDate><t:EndDate>2026-09-25</t:EndDate>"
        )
    )
    assert {start.day for start, _ in iter_booking_occurrences(own)} == {11, 25}
    own["recurrence_complete"] = False
    result = booking_coverage(payload(), [own])
    assert result.uncertain
    assert not result.covered


def test_same_course_conflict_requires_uid_not_title_or_time() -> None:
    own = booking()
    other = booking(uid="other-series", outlook_booking_id="other-master", recurrence=None)
    assert detect_payload_conflicts(payload(), [other], auto_bookings=[own])
    room_copy = booking(title="Organizer name", recurrence=None, outlook_booking_id="room-copy")
    assert not detect_payload_conflicts(payload(), [room_copy], auto_bookings=[own])
    room_copy["organizer_mailbox"] = "different@example.com"
    assert detect_payload_conflicts(payload(), [room_copy], auto_bookings=[own])


def test_excess_tail_is_reported_even_when_requested_dates_are_covered() -> None:
    own = booking(recurrence={**payload()["recurrence"], "until_date": "2026-12-25"})
    assert find_matching_auto_booking(payload(), [own]) == own
    assert find_extra_auto_bookings([own], [payload()]) == [own]


def zubkova_slots():
    sections = SectionsConfig.model_validate(
        {
            "sections": [
                {
                    "code": "core",
                    "name": "Core",
                    "programs": [{"code": "Y1", "name": "Y1", "groups": [f"B26-MFAI-0{i}" for i in range(1, 6)]}],
                }
            ]
        }
    )
    term = TermConfig.model_validate(
        {"name": "Fall", "semester": {"start_date": "2026-09-11", "end_date": "2026-09-25"}}
    )
    sessions = []
    for group, start, end in [
        (3, "12:40", "14:10"),
        (1, "14:20", "15:50"),
        (5, "16:00", "17:30"),
        (4, "17:40", "19:10"),
    ]:
        sessions.append(
            {
                "audience": [f"B26-MFAI-0{group}"],
                "weekly_pattern": [
                    {
                        "weekday": "FRIDAY",
                        "start_time": start,
                        "end_time": end,
                        "room": "209",
                        "instructor": "Svetlana Zubkova",
                    }
                ],
            }
        )
    courses = CoursesConfig.model_validate(
        {
            "courses": [
                {
                    "name": "Algebra",
                    "section_code": "core",
                    "components": [
                        {
                            "tag": "lab",
                            "audience": [],
                            "sessions": sessions,
                        }
                    ],
                }
            ]
        }
    )
    return build_bookable_slots(courses, sections, term, {"209"})


def as_dto(data: dict) -> BookingDTO:
    recurrence = data["recurrence"]
    return BookingDTO.model_validate(
        {
            **data,
            "recurrence": (
                f"<t:WeeklyRecurrence><t:DaysOfWeek>{recurrence['weekday'].title()}</t:DaysOfWeek></t:WeeklyRecurrence>"
                f"<t:StartDate>{recurrence['start_date']}</t:StartDate><t:EndDate>{recurrence['until_date']}</t:EndDate>"
            ),
        }
    )


def test_zubkova_209_four_slots_only_first_last_pending() -> None:
    slots = zubkova_slots()
    auto = [
        as_dto(
            booking(
                **{
                    **slot.payload,
                    "title": f"Auto: {slot.payload['title']}",
                    "outlook_booking_id": f"master-{i}",
                    "uid": f"uid-{i}",
                }
            )
        )
        for i, slot in enumerate(slots)
        if i in {0, 3}
    ]
    index = build_review_index(slots, auto_bookings=auto, existing_bookings=[])
    rows = [
        row
        for program in index.tree.programs
        for course in program.courses
        for component in course.components
        for row in component.slots
    ]
    by_time = {row.start_time: row for row in rows}
    assert by_time["12:40:00"].review_kind == "pending_approval"
    assert by_time["17:40:00"].review_kind == "pending_approval"
    for clock in ("14:20:00", "16:00:00"):
        assert by_time[clock].review_kind == "ready"
        assert by_time[clock].missing_dates == ["2026-09-11", "2026-09-18", "2026-09-25"]
    submitted = collect_booking_payloads(index, [slot.slot_id for slot in slots], {})
    assert [dtm.datetime.fromisoformat(item["start"]).strftime("%H:%M") for item in submitted] == ["14:20", "16:00"]


@pytest.mark.parametrize(
    ("response", "kind"),
    [("Accept", "booked"), ("Tentative", "pending_approval"), ("Unknown", "unknown"), ("Decline", "declined")],
)
def test_review_keeps_room_response_separate_from_presence(response, kind) -> None:
    slot = zubkova_slots()[0]
    own = as_dto(booking(**slot.payload, room_response=response))
    index = build_review_index([slot], auto_bookings=[own], existing_bookings=[])
    row = index.tree.programs[0].courses[0].components[0].slots[0]
    assert row.review_kind == kind
    assert row.room_presence == "present"
    assert row.covered_dates == row.occurrence_dates
    assert not collect_booking_payloads(index, [slot.slot_id], {})


def test_review_deleted_instance_is_missing_and_cannot_resubmit_master() -> None:
    slot = zubkova_slots()[0]
    own = as_dto(booking(**slot.payload, room_response="Accept", deleted_occurrences=["2026-09-18"]))
    index = build_review_index([slot], auto_bookings=[own], existing_bookings=[])
    row = index.tree.programs[0].courses[0].components[0].slots[0]
    assert row.review_kind == "unknown"
    assert row.covered_dates == ["2026-09-11", "2026-09-25"]
    assert row.missing_dates == ["2026-09-18"]
    assert not collect_booking_payloads(index, [slot.slot_id], {})


def test_missing_master_exception_metadata_is_unknown() -> None:
    slot = zubkova_slots()[0]
    data = booking(**slot.payload, room_response="Accept")
    data.pop("recurrence_complete")
    index = build_review_index([slot], auto_bookings=[as_dto(data)], existing_bookings=[])
    row = index.tree.programs[0].courses[0].components[0].slots[0]
    assert row.review_kind == "unknown"
    assert row.missing_dates == row.occurrence_dates


def test_accepted_but_absent_room_is_unknown_not_booked() -> None:
    slot = zubkova_slots()[0]
    own = as_dto(booking(**slot.payload, room_response="Accept", room_presence="absent"))
    index = build_review_index([slot], auto_bookings=[own], existing_bookings=[])
    assert index.slots[slot.slot_id].review_kind == "unknown"


def test_excess_series_retaining_teaching_dates_cannot_cancel_master() -> None:
    slot = zubkova_slots()[0]
    data = booking(**slot.payload, can_cancel=True)
    data["recurrence"] = {**data["recurrence"], "until_date": "2026-10-02"}
    index = build_review_index([slot], auto_bookings=[as_dto(data)], existing_bookings=[])
    assert len(index.extras) == 1
    assert next(iter(index.extras.values()))["can_cancel"] is False


def test_split_preserves_biweekly_anchor_and_exact_exception_dates() -> None:
    slot = zubkova_slots()[0]
    slot.payload["recurrence"]["interval"] = 2
    slot.payload["recurrence"]["until_date"] = "2026-10-23"
    original = iter_payload_occurrences(slot.payload)
    conflict = original[1]
    split = split_payloads_around_conflicts(slot, [(conflict[0], conflict[1], [])])
    actual = {occurrence for part in split for occurrence in iter_payload_occurrences(part)}
    assert actual == set(original) - {conflict}
