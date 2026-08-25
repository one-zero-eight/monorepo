import datetime as dtm

import pytest
from fastapi.testclient import TestClient

from scripts.when2meet.backfill_archive_after import (
    apply_candidates,
    calculate_document_archive_after,
    collect_candidates,
)
from src.common_beanie import BeanieStore


def test_backfill_uses_selected_time_end():
    archive_after = calculate_document_archive_after(
        {
            "slots": [dtm.datetime(2027, 6, 15, 10, tzinfo=dtm.UTC)],
            "selected_time": {
                "start": "2027-06-16T12:00:00Z",
                "end": "2027-06-16T13:30:00Z",
            },
        }
    )

    assert archive_after == dtm.datetime(2027, 6, 16, 13, 30, tzinfo=dtm.UTC)


def test_backfill_uses_latest_slot_plus_thirty_minutes():
    archive_after = calculate_document_archive_after(
        {
            "slots": [
                dtm.datetime(2027, 6, 15, 12, tzinfo=dtm.UTC),
                dtm.datetime(2027, 6, 15, 10, tzinfo=dtm.UTC),
            ]
        }
    )

    assert archive_after == dtm.datetime(2027, 6, 15, 12, 30, tzinfo=dtm.UTC)


def test_backfill_rejects_document_without_slots():
    with pytest.raises(KeyError):
        calculate_document_archive_after({})


def test_backfill_rejects_empty_slots_without_selected_time():
    with pytest.raises(ValueError, match="without meeting slots"):
        calculate_document_archive_after({"slots": []})


def test_backfill_updates_only_documents_missing_archive_after(when2meet_client: TestClient):
    portal = when2meet_client.portal
    assert portal is not None
    store: BeanieStore = when2meet_client.app.state.beanie_store

    async def exercise_backfill():
        database = store.client.get_database(store.current_database_name)
        collection = database.get_collection("events")
        missing_id = (
            await collection.insert_one(
                {
                    "name": "Legacy",
                    "slug": "legacy",
                    "slots": [dtm.datetime(2027, 6, 15, 10, tzinfo=dtm.UTC)],
                }
            )
        ).inserted_id
        existing_archive_after = dtm.datetime(2028, 1, 1, tzinfo=dtm.UTC)
        existing_id = (
            await collection.insert_one(
                {
                    "name": "Current",
                    "slug": "current",
                    "slots": [dtm.datetime(2027, 6, 15, 10, tzinfo=dtm.UTC)],
                    "archive_after": existing_archive_after,
                }
            )
        ).inserted_id

        candidates, invalid = await collect_candidates(collection)
        assert invalid == []
        assert [candidate.event_id for candidate in candidates] == [missing_id]

        assert await apply_candidates(collection, candidates) == 1
        assert await apply_candidates(collection, candidates) == 0

        missing_document = await collection.find_one({"_id": missing_id})
        existing_document = await collection.find_one({"_id": existing_id})
        assert missing_document is not None
        assert existing_document is not None
        assert missing_document["archive_after"] == dtm.datetime(2027, 6, 15, 10, 30, tzinfo=dtm.UTC)
        assert existing_document["archive_after"] == existing_archive_after

    portal.call(exercise_backfill)
