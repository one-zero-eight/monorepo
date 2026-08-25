import argparse
import asyncio
import datetime as dtm
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter, ValidationError
from pymongo import AsyncMongoClient, UpdateOne

from src.when2meet.config import settings
from src.when2meet.modules.events.archive import calculate_archive_after
from src.when2meet.modules.events.schemas import MeetingTime, normalize_datetime

MISSING_ARCHIVE_AFTER = {"archive_after": {"$exists": False}}
SLOTS_ADAPTER = TypeAdapter(list[dtm.datetime])


@dataclass(frozen=True)
class BackfillCandidate:
    event_id: Any
    archive_after: dtm.datetime


def calculate_document_archive_after(document: Mapping[str, Any]) -> dtm.datetime:
    slots = [normalize_datetime(slot) for slot in SLOTS_ADAPTER.validate_python(document["slots"])]
    selected_time_raw = document.get("selected_time")
    selected_time = MeetingTime.model_validate(selected_time_raw) if selected_time_raw is not None else None
    return calculate_archive_after(slots, selected_time)


async def collect_candidates(collection: Any) -> tuple[list[BackfillCandidate], list[tuple[Any, str]]]:
    candidates: list[BackfillCandidate] = []
    invalid: list[tuple[Any, str]] = []
    cursor = collection.find(
        MISSING_ARCHIVE_AFTER,
        projection={"slots": True, "selected_time": True},
    )
    async for document in cursor:
        try:
            archive_after = calculate_document_archive_after(document)
        except (KeyError, TypeError, ValueError, ValidationError) as error:
            invalid.append((document["_id"], str(error)))
            continue
        candidates.append(BackfillCandidate(document["_id"], archive_after))
    return candidates, invalid


async def apply_candidates(collection: Any, candidates: list[BackfillCandidate]) -> int:
    if not candidates:
        return 0
    result = await collection.bulk_write(
        [
            UpdateOne(
                {"_id": candidate.event_id, **MISSING_ARCHIVE_AFTER},
                {"$set": {"archive_after": candidate.archive_after}},
            )
            for candidate in candidates
        ],
        ordered=False,
    )
    return result.modified_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill archive_after for legacy When2Meet events")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Without this flag the script only validates and reports.",
    )
    return parser.parse_args()


async def run(apply: bool) -> int:
    client = AsyncMongoClient(
        settings.mongo.uri.get_secret_value(),
        connectTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )
    database = client.get_default_database(default=settings.service_name)
    collection = database.get_collection("events")
    try:
        await client.admin.command("ping")
        candidates, invalid = await collect_candidates(collection)

        print(f"Database: {database.name}")
        print(f"Documents without archive_after: {len(candidates) + len(invalid)}")
        print(f"Valid candidates: {len(candidates)}")
        print(f"Invalid documents: {len(invalid)}")

        if invalid:
            for event_id, error in invalid[:20]:
                print(f"Invalid event {event_id}: {error}")
            if len(invalid) > 20:
                print(f"... and {len(invalid) - 20} more invalid documents")
            print("No changes were written.")
            return 1

        if not apply:
            print("Dry run complete. Run again with --apply to write changes.")
            return 0

        modified_count = await apply_candidates(collection, candidates)
        remaining_count = await collection.count_documents(MISSING_ARCHIVE_AFTER)
        print(f"Updated documents: {modified_count}")
        print(f"Documents still missing archive_after: {remaining_count}")
        if remaining_count == 0:
            return 0
        return 1
    finally:
        await client.close()


def main() -> int:
    args = parse_args()
    return asyncio.run(run(apply=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
