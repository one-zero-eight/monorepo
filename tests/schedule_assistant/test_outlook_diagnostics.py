import datetime as dtm
from types import SimpleNamespace
from unittest.mock import Mock

import exchangelib

from scripts.schedule_assistant.diagnose_outlook import calendar_records, compare_items, identity_token

UTC = dtm.UTC


def event(uid: str, subject: str = "Course", *, item_id: str = "item") -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id,
        uid=uid,
        subject=subject,
        start=dtm.datetime(2026, 9, 11, 9, 40, tzinfo=UTC),
        end=dtm.datetime(2026, 9, 11, 11, 10, tzinfo=UTC),
        type="Occurrence",
        my_response_type="Tentative",
        legacy_free_busy_status="Tentative",
        is_cancelled=False,
        required_attendees=[
            SimpleNamespace(mailbox=SimpleNamespace(email_address="room@example.org"), response_type="Tentative")
        ],
        resources=[],
    )


def test_diagnostic_matches_uid_not_changed_subject():
    source = event("same", "Course")
    room = event("same", "Organizer Course", item_id="room-copy")
    rows = compare_items([source], [room], "room@example.org")
    assert rows[0]["room_presence"] == "present"
    assert rows[0]["room_copies"][0]["item_token"] != rows[0]["item_token"]
    assert rows[0]["response"] == "Tentative"


def test_diagnostic_does_not_match_unrelated_same_slot_event():
    rows = compare_items([event("first")], [event("second")], "room@example.org")
    assert rows[0]["room_presence"] == "absent"
    assert rows[0]["room_copies"] == []


def test_diagnostic_redacts_raw_exchange_identifiers():
    assert identity_token(None) is None
    original = event("private-uid")
    rows = compare_items([original], [], "room@example.org")
    assert rows[0]["uid_token"] != original.uid
    assert len(rows[0]["uid_token"]) == 20


def test_diagnostic_splits_capped_views_and_deduplicates_boundary_events(monkeypatch):
    monkeypatch.setattr("scripts.schedule_assistant.diagnose_outlook.READ_LIMIT", 2)
    first = event("first", item_id="first")
    second = event("second", item_id="second")
    account = Mock(spec=exchangelib.Account)
    account.calendar.view.return_value.only.side_effect = [[first, second], [first], [second]]
    start = dtm.datetime(2026, 9, 11, tzinfo=UTC)
    records = calendar_records(account, start, start + dtm.timedelta(days=1))
    assert {item.uid for item in records} == {"first", "second"}
