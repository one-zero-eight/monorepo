import datetime as dtm

import pytest
from pydantic import ValidationError

from src.when2meet.modules.events.schemas import EventCreate, EventUpdate, ParticipantUpdate

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
