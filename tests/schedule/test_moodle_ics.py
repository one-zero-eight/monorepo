from pathlib import Path

import icalendar

from src.schedule.modules.ics.utils import fix_moodle_events

FIXTURE = Path(__file__).parent / "fixtures" / "moodle_export.ics"


def _summaries(calendar: icalendar.Calendar) -> list[str]:
    return [str(event.get("summary")) for event in calendar.walk("VEVENT")]


def test_fix_moodle_events_pairs_feedback_per_course():
    raw = icalendar.Calendar.from_ical(FIXTURE.read_bytes())
    fixed = fix_moodle_events(raw)
    summaries = _summaries(fixed)

    feedback = [s for s in summaries if s.startswith("Feedback - ")]
    feedback_courses = {s.removeprefix("Feedback - ") for s in feedback}

    assert len(feedback) == 7
    assert feedback_courses == {
        "DatStrAndAlg",
        "MatAnaII",
        "AnaGeoAndLinAlgII",
        "TheComSci",
        "SofSysAnaAndDes",
        "SofEngToo",
        "SofPro",
    }


def test_fix_moodle_events_orphan_close_becomes_deadline():
    raw = icalendar.Calendar.from_ical(FIXTURE.read_bytes())
    fixed = fix_moodle_events(raw)
    summaries = _summaries(fixed)

    assert any("Exercise Physiology Quiz закрывается" in s and "PhyEduAndSpoEn" in s for s in summaries)


def test_fix_moodle_events_keeps_assignment_deadlines():
    raw = icalendar.Calendar.from_ical(FIXTURE.read_bytes())
    fixed = fix_moodle_events(raw)
    summaries = _summaries(fixed)

    assert "Assignment 5 is due - SofPro" in summaries
    assert "Lo-Fi Prototype (Midterm) is due - UX/DesBs" in summaries


def test_fix_moodle_events_skips_attendance():
    raw = icalendar.Calendar.from_ical(FIXTURE.read_bytes())
    fixed = fix_moodle_events(raw)
    summaries = _summaries(fixed)

    assert not any("Attendance" in s for s in summaries)


def test_fix_moodle_events_does_not_drop_events_on_name_collision():
    raw = icalendar.Calendar.from_ical(FIXTURE.read_bytes())
    input_count = sum(1 for _ in raw.walk("VEVENT"))
    fixed = fix_moodle_events(raw)
    output_count = sum(1 for _ in fixed.walk("VEVENT"))

    assert input_count == 31
    assert output_count == 23
