import datetime as dtm

import pytest
from pydantic import ValidationError

from src.when2meet.modules.events.schemas import EventCreate, EventUpdate, MeetingTime, ParticipantUpdate

NAIVE_SLOT = dtm.datetime.fromisoformat("2026-06-15T09:00:00")


def test_event_create_normalizes_and_sorts_slots():
    event = EventCreate(
        name="Planning",
        slots=[
            dtm.datetime(2026, 6, 15, 14, 0, 0, 123456, tzinfo=dtm.timezone(dtm.timedelta(hours=4))),
            NAIVE_SLOT,
        ],
    )

    assert event.slots == [
        dtm.datetime(2026, 6, 15, 9, 0, tzinfo=dtm.UTC),
        dtm.datetime(2026, 6, 15, 10, 0, tzinfo=dtm.UTC),
    ]


def test_event_update_keeps_missing_slots_unset():
    event_update = EventUpdate(name="Renamed")

    assert event_update.model_dump(exclude_unset=True) == {"name": "Renamed"}


def test_event_update_accepts_explicit_null_slots():
    event_update = EventUpdate(slots=None)

    assert event_update.model_dump(exclude_unset=True) == {"slots": None}


def test_meeting_time_normalizes_and_rejects_empty_interval():
    meeting_time = MeetingTime(
        start=dtm.datetime(2026, 6, 15, 14, 0, 0, 123456, tzinfo=dtm.timezone(dtm.timedelta(hours=4))),
        end=NAIVE_SLOT.replace(hour=11, minute=30),
    )

    assert meeting_time.start == dtm.datetime(2026, 6, 15, 10, 0, tzinfo=dtm.UTC)
    assert meeting_time.end == dtm.datetime(2026, 6, 15, 11, 30, tzinfo=dtm.UTC)

    with pytest.raises(ValidationError):
        MeetingTime(start=NAIVE_SLOT, end=NAIVE_SLOT)


def test_participant_update_normalizes_availability_without_reordering():
    participant_update = ParticipantUpdate(
        availability=[
            dtm.datetime(2026, 6, 15, 14, 0, tzinfo=dtm.timezone(dtm.timedelta(hours=4))),
            NAIVE_SLOT,
        ],
    )

    assert participant_update.availability == [
        dtm.datetime(2026, 6, 15, 10, 0, tzinfo=dtm.UTC),
        dtm.datetime(2026, 6, 15, 9, 0, tzinfo=dtm.UTC),
    ]


def test_event_create_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        EventCreate.model_validate({"name": "Planning", "slots": [NAIVE_SLOT], "owner_id": "other-user"})
