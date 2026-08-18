import datetime as dtm

from src.schedule_assistant.core_courses.location_parser import parse_location_string


def test_do_with_clock_time_is_till():
    item = parse_location_string("ОНЛАЙН ДО 13:00")
    assert item is not None
    assert item.location == "ОНЛАЙН"
    assert item.till == dtm.time(13, 0)
    assert item.ends_on is None


def test_do_with_date_stays_ends_on():
    item = parse_location_string("ОНЛАЙН ДО 01/12")
    assert item is not None
    assert item.location == "ОНЛАЙН"
    assert item.ends_on is not None
    assert item.ends_on.month == 12
    assert item.ends_on.day == 1
    assert item.till is None
