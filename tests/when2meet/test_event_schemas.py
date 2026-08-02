import datetime as dtm

import pytest
from pydantic import ValidationError

from src.when2meet.modules.events.schemas import EventCreate, EventUpdate, MeetingTime, ParticipantUpdate

NAIVE_SLOT = dtm.datetime.fromisoformat("2026-06-15T09:00:00")
AWARE_SLOT = dtm.datetime(2026, 6, 15, 9, 0, tzinfo=dtm.UTC)


def test_event_create_normalizes_and_sorts_slots_without_changing_timezone():
    event = EventCreate(
        name="Planning",
        slots=[
            dtm.datetime(2026, 6, 15, 14, 0, 0, 123456, tzinfo=dtm.timezone(dtm.timedelta(hours=4))),
            AWARE_SLOT,
        ],
    )

    assert event.slots == [
        dtm.datetime(2026, 6, 15, 9, 0, tzinfo=dtm.UTC),
        dtm.datetime(2026, 6, 15, 14, 0, tzinfo=dtm.timezone(dtm.timedelta(hours=4))),
    ]


def test_event_update_keeps_missing_slots_unset():
    event_update = EventUpdate(name="Renamed")

    assert event_update.model_dump(exclude_unset=True) == {"name": "Renamed"}


def test_event_update_accepts_explicit_null_slots():
    event_update = EventUpdate(slots=None)

    assert event_update.model_dump(exclude_unset=True) == {"slots": None}


def test_meeting_time_preserves_timezone_and_rejects_empty_interval():
    meeting_time = MeetingTime(
        start="2026-06-15T14:00:00.123456+04:00",
        end="2026-06-15T11:30:00Z",
    )

    assert meeting_time.start == "2026-06-15T14:00:00+04:00"
    assert meeting_time.end == "2026-06-15T11:30:00Z"
    assert meeting_time.start_datetime == dtm.datetime(2026, 6, 15, 14, 0, tzinfo=dtm.timezone(dtm.timedelta(hours=4)))
    assert meeting_time.end_datetime == dtm.datetime(2026, 6, 15, 11, 30, tzinfo=dtm.UTC)

    with pytest.raises(ValidationError):
        MeetingTime(start="2026-06-15T09:00:00Z", end="2026-06-15T09:00:00Z")


def test_participant_update_normalizes_availability_without_reordering_or_changing_timezone():
    participant_update = ParticipantUpdate(
        availability=[
            dtm.datetime(2026, 6, 15, 14, 0, tzinfo=dtm.timezone(dtm.timedelta(hours=4))),
            AWARE_SLOT,
        ],
    )

    assert participant_update.availability == [
        dtm.datetime(2026, 6, 15, 14, 0, tzinfo=dtm.timezone(dtm.timedelta(hours=4))),
        dtm.datetime(2026, 6, 15, 9, 0, tzinfo=dtm.UTC),
    ]


def test_datetime_fields_reject_missing_timezone():
    with pytest.raises(ValidationError):
        EventCreate(name="Planning", slots=[NAIVE_SLOT])

    with pytest.raises(ValidationError):
        EventUpdate(slots=[NAIVE_SLOT])

    with pytest.raises(ValidationError):
        MeetingTime(start="2026-06-15T09:00:00", end="2026-06-15T10:00:00")

    with pytest.raises(ValidationError):
        ParticipantUpdate(availability=[NAIVE_SLOT])


def test_event_create_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        EventCreate.model_validate({"name": "Planning", "slots": [AWARE_SLOT], "owner_id": "other-user"})
