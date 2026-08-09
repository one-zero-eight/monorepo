import datetime as dtm

import icalendar
import pytest

from src.schedule.utils import (
    aware_utcnow,
    get_current_year,
    locate_ics_by_path,
    validate_vevent,
)


def _minimal_vevent() -> icalendar.Event:
    event = icalendar.Event()
    event.add("uid", "test@example.com")
    event.add("dtstart", icalendar.vDatetime(dtm.datetime(2025, 1, 1, 10, 0, tzinfo=dtm.UTC)))
    event.add("dtend", icalendar.vDatetime(dtm.datetime(2025, 1, 1, 11, 0, tzinfo=dtm.UTC)))
    return event


def test_validate_vevent_rejects_missing_uid():
    event = _minimal_vevent()
    del event["uid"]
    with pytest.raises(ValueError, match="UID"):
        validate_vevent(event)


def test_validate_vevent_rejects_missing_dtstart():
    event = _minimal_vevent()
    del event["dtstart"]
    with pytest.raises(ValueError, match="DTSTART"):
        validate_vevent(event)


def test_validate_vevent_accepts_minimal_event():
    validate_vevent(_minimal_vevent())


def test_validate_vevent_accepts_all_day_vdate_without_value_param():
    event = icalendar.Event()
    event.add("uid", "all-day@example.com")
    event.add("dtstart", icalendar.vDate(dtm.date(2025, 1, 1)))
    assert event["DTSTART"].params.get("VALUE") != "DATE"
    validate_vevent(event)


def test_locate_ics_by_path_rejects_parent_traversal(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from src.schedule.config import settings

    monkeypatch.setattr(settings, "predefined_dir", tmp_path)
    with pytest.raises(ValueError, match="escapes predefined ICS directory"):
        locate_ics_by_path("../secret.ics")


def test_locate_ics_by_path_rejects_non_ics_extension(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from src.schedule.config import settings

    monkeypatch.setattr(settings, "predefined_dir", tmp_path)
    with pytest.raises(ValueError, match="must point to an .ics file"):
        locate_ics_by_path("notes.txt")


def test_get_current_year_is_recent():
    year = get_current_year()
    assert year >= 2025


def test_aware_utcnow_is_timezone_aware():
    now = aware_utcnow()
    assert now.tzinfo is not None
