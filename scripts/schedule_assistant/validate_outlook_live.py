"""Controlled live room-209 experiments; only isolated TEST Schedule Assistant items.

Requires --execute and a new private /tmp journal. Complete uncached reads establish
availability in BOTH calendars. Durable markers precede every possible mutation;
uncertain writes are never retried. All scenarios clean up before the next starts.
A successful exit requires scenario assertions AND verified two-calendar cleanup.
"""

# ruff: noqa: BLE001, S108 — exclusive 0600 journal creation and atomic private replacement
import argparse
import asyncio
import datetime as dtm
import json
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import exchangelib
import exchangelib.errors
from exchangelib.protocol import BaseProtocol
from exchangelib.recurrence import NumberedPattern, Recurrence, WeeklyPattern

from scripts.schedule_assistant.diagnose_outlook import MSK, calendar_records, identity_token


def save_journal(path: Path, data: dict) -> None:
    """Atomic private replacement preserves recovery identities if interrupted."""
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as output:
        json.dump(data, output, indent=2)
        output.flush()
        os.fsync(output.fileno())
        temporary = output.name
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


class LiveValidation:
    def __init__(self, journal: Path, *, resume: bool = False):
        from src.room_booking.config import settings
        from src.room_booking.modules.bmp.repository import BmpCalendarRepository
        from src.room_booking.modules.rooms.repository import room_repository

        BaseProtocol.TIMEOUT = 30
        room = room_repository.get_by_id("209")
        if room is None:
            raise ValueError("Room 209 is not configured")
        self.room = room
        config = settings.exchange
        self.repository = BmpCalendarRepository(
            config.ews_endpoint, config.bmp.username, config.bmp.password.get_secret_value()
        )
        self.room_account = exchangelib.Account(
            self.room.resource_email,
            autodiscover=False,
            access_type=exchangelib.DELEGATE,
            config=self.repository.account.protocol.config,
        )
        self.journal = journal
        self.state: dict[str, Any] = {"room": "209", "phase": "intent", "items": [], "evidence": []}
        if resume:
            require(
                journal.stat().st_uid == os.getuid() and journal.stat().st_mode & 0o077 == 0,
                "Journal must be private and owned",
            )
            self.state = json.loads(journal.read_text())
            require(self.state["room"] == "209", "Recovery room mismatch")
        else:
            descriptor = os.open(journal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(descriptor)
            save_journal(journal, self.state)

    def record(self, phase: str, **data: Any) -> None:
        evidence = {"phase": phase, "at": dtm.datetime.now(MSK).isoformat(), **data}
        self.state["phase"] = phase
        self.state["evidence"].append(evidence)
        save_journal(self.journal, self.state)
        print(json.dumps(evidence), flush=True)

    async def read_only(self, function: Any, *args: Any) -> Any:
        for attempt in range(3):
            try:
                return await asyncio.to_thread(function, *args)
            except exchangelib.errors.ErrorTimeoutExpired:
                self.record("read_timeout", attempt=attempt + 1, outcome="unknown; read-only retry, never a write")
                if attempt == 2:
                    raise
                await asyncio.sleep(5)
        raise RuntimeError("Read did not complete")

    async def window(self, start: dtm.datetime, end: dtm.datetime) -> dict[str, list[Any]]:
        result = {}
        for source, account in (("organizer", self.repository.account), ("room", self.room_account)):
            result[source] = await self.read_only(calendar_records, account, start, end)
        return result

    async def free(self, start: dtm.datetime, end: dtm.datetime, allowed: list[dict] | None = None) -> bool:
        observations = await self.window(start, end)
        for items in observations.values():
            for item in items:
                if item.is_cancelled or not (item.start < end and item.end > start):
                    continue
                if any(own["uid"] and item.uid == own["uid"] for own in (allowed or [])):
                    continue
                return False
        return True

    async def select_start(self, start: dtm.datetime, *, recurring: bool = False) -> dtm.datetime:
        now = dtm.datetime.now(MSK)
        for day in range(7):
            candidate = start + dtm.timedelta(days=day)
            if not now < candidate < now + dtm.timedelta(days=7):
                continue
            intervals = [candidate]
            if recurring:
                intervals.append(candidate + dtm.timedelta(days=7))
            if all([await self.free(value, value + dtm.timedelta(minutes=20)) for value in intervals]):
                self.record("availability_verified", starts=[value.isoformat() for value in intervals], minutes=20)
                return candidate
        raise RuntimeError("No verified free early window in the next seven days; no writes performed")

    def entry(self, start: dtm.datetime, *, recurring: bool = False) -> tuple[Any, dict]:
        from src.room_booking.modules.bmp.repository import BmpBatchCreateEntry

        operation_id = f"test-schedule-assistant-{uuid.uuid4()}"
        recurrence = None
        if recurring:
            recurrence = Recurrence(
                pattern=WeeklyPattern(interval=1, weekdays=[start.isoweekday()], first_day_of_week=1),
                boundary=NumberedPattern(start=start.date(), number=2),
            )
        entry = BmpBatchCreateEntry(
            room=self.room,
            start=start,
            end=start + dtm.timedelta(minutes=2),
            title=f"TEST Schedule Assistant {operation_id}",
            participant_emails=[],
            operation_id=operation_id,
            recurrence=recurrence,
        )
        row = {
            "operation_id": operation_id,
            "title": entry.title,
            "start": entry.start.isoformat(),
            "end": entry.end.isoformat(),
            "occurrences": 2 if recurring else 1,
            "uid": None,
            "outlook_booking_id": None,
            "creation_started": False,
        }
        self.state["items"].append(row)
        save_journal(self.journal, self.state)
        return entry, row

    def identity(self, row: dict, *, occurrence: int | None = None) -> Any:
        from src.room_booking.modules.bookings.schemas import ReconcileBookingEntry

        offset = dtm.timedelta(days=7 * (occurrence or 0))
        return ReconcileBookingEntry(
            operation_id=row["operation_id"],
            uid=row["uid"],
            outlook_booking_id=row["outlook_booking_id"],
            room_id="209",
            start=dtm.datetime.fromisoformat(row["start"]) + offset,
            end=dtm.datetime.fromisoformat(row["end"]) + offset,
            scope="series" if occurrence is None else "occurrence",
        )

    def remember(self, row: dict, booking: Any) -> None:
        if booking is not None:
            row["uid"] = booking.uid or row["uid"]
            row["outlook_booking_id"] = booking.outlook_booking_id or row["outlook_booking_id"]
        save_journal(self.journal, self.state)

    async def create(self, pairs: list[tuple[Any, dict]], *, label: str, allowed: list[dict] | None = None) -> None:
        # Re-check immediately before every potentially mutating call; replay
        # permits only the positively identified original test event.
        for entry, row in pairs:
            for occurrence in range(row["occurrences"]):
                offset = dtm.timedelta(days=7 * occurrence)
                require(await self.free(entry.start + offset, entry.end + offset, allowed), "Availability changed")
            row["creation_started"] = True
        self.record("create_intent", label=label, operations=[row["operation_id"] for _, row in pairs])
        results = []
        async for index, result, sent in self.repository.iter_create_bookings_batch([entry for entry, _ in pairs]):
            for entry, row in pairs:
                self.remember(row, entry.sent_booking)
            if result is not None:
                if index is None:
                    raise AssertionError("Result without entry index")
                self.remember(pairs[index][1], result.booking)
                observation = {
                    "index": index,
                    "status": result.status,
                    "response": result.booking.room_response if result.booking else None,
                    "has_error": bool(result.error),
                    "send_diagnostic": pairs[index][0].send_error,
                    "uid_token": identity_token(pairs[index][1]["uid"]),
                }
                results.append(observation)
                self.record("create_result", label=label, **observation)
            elif sent is not None:
                self.record("identity_persisted", label=label, indexes=sent)
        require(len(results) == len(pairs), "Missing create results")
        require(
            all(result["status"] == "ok" and not result["has_error"] for result in results), "Create outcome uncertain"
        )
        require(all(row["uid"] and row["outlook_booking_id"] for _, row in pairs), "Missing durable identity")

    async def observe(self, row: dict, *, occurrence: int | None = None, label: str) -> Any:
        result = await self.repository.reconcile_booking(self.identity(row, occurrence=occurrence))
        self.remember(row, result)
        self.record(
            "reconciled",
            label=label,
            uid_token=identity_token(row["uid"]),
            status=result.status,
            organizer=result.organizer_presence,
            room=result.room_presence,
            response=result.room_response,
            has_error=bool(result.error),
        )
        require(result.status == "ok" and not result.error, "Reconciliation incomplete")
        return result

    async def counts(self, row: dict, occurrence: int) -> dict[str, int]:
        identity = self.identity(row, occurrence=occurrence)
        observations = await self.window(identity.start, identity.end)
        return {
            source: sum(
                1
                for item in items
                if (row["uid"] and item.uid == row["uid"]) or row["operation_id"] in (item.subject or "")
            )
            for source, items in observations.items()
        }

    async def expect_counts(self, row: dict, occurrence: int, expected: dict[str, int], *, label: str) -> None:
        for attempt in range(19):
            counts = await self.counts(row, occurrence)
            self.record("calendar_counts", label=label, occurrence=occurrence, attempt=attempt + 1, **counts)
            if counts == expected:
                return
            if attempt < 18:
                await asyncio.sleep(5)
        raise AssertionError(f"{label}: complete calendar counts did not reach {expected}")

    async def cancel(self, row: dict, *, occurrence: int | None = None, label: str) -> Any:
        from src.room_booking.modules.bookings.schemas import ScopedCancelBookingRequest

        self.record("cancel_intent", label=label, operation=row["operation_id"], occurrence=occurrence)
        result = await self.repository.cancel_scoped_booking(
            ScopedCancelBookingRequest(**self.identity(row, occurrence=occurrence).model_dump())
        )
        self.record(
            "cancel_result",
            label=label,
            status=result.cancellation_status,
            has_error=bool(result.error),
            diagnostic=[text for text in result.evidence if text.startswith("Cancellation send raised")],
        )
        require(result.cancellation_status != "requires_review", "Cancellation outcome unknown; no blind retry")
        return result

    async def safety_item(self, row: dict) -> Any:
        items = await self.read_only(self.repository._find_identity_items, self.identity(row))
        if not items:
            return None
        require(len(items) == 1, "Ambiguous cleanup identity")
        item: Any = items[0]
        attendees = [*(item.required_attendees or []), *(item.resources or []), *(item.optional_attendees or [])]
        require(
            item.subject == f"Auto: {row['title']}"
            and item.start == dtm.datetime.fromisoformat(row["start"])
            and item.end == dtm.datetime.fromisoformat(row["end"])
            and all(
                attendee.mailbox.email_address.casefold() == self.room.resource_email.casefold()
                for attendee in attendees
            )
            and bool(item.recurrence) == (row["occurrences"] == 2),
            "Cleanup identity safety check failed",
        )
        row["uid"] = str(item.uid) if item.uid else row["uid"]
        row["outlook_booking_id"] = str(item.id)
        save_journal(self.journal, self.state)
        return item

    async def cleanup(self) -> bool:
        complete = True
        for row in reversed(self.state["items"]):
            if not row["creation_started"]:
                continue
            try:
                item = await self.safety_item(row)
                if item is not None:
                    await self.cancel(row, label="final_series_cleanup")
                for occurrence in range(row["occurrences"]):
                    await self.expect_counts(row, occurrence, {"organizer": 0, "room": 0}, label="cleanup_verified")
                # A bounded occurrence view alone cannot exclude an orphan master.
                require(
                    not await asyncio.to_thread(self.repository._find_identity_items, self.identity(row)),
                    "Organizer master remains",
                )
                if row["uid"]:
                    presence, _ = await asyncio.to_thread(
                        self.repository._read_room_presence, self.room, row["uid"], None, None, "series"
                    )
                    require(presence == "absent", "Room master remains")
                self.record("item_cleaned", uid_token=identity_token(row["uid"]))
            except Exception as error:
                complete = False
                self.record("cleanup_blocked", error_type=type(error).__name__, operation=row["operation_id"])
        self.record("cleaned" if complete else "requires_manual_cleanup")
        return complete

    async def batch(self, start: dtm.datetime) -> None:
        pairs = [self.entry(start + dtm.timedelta(minutes=2 * index)) for index in range(4)]
        await self.create(pairs, label="batch_four")
        for _, row in pairs:
            await self.expect_counts(row, 0, {"organizer": 1, "room": 1}, label="batch_present")
        await self.replay_checks(start, pairs)

    async def replay(self, start: dtm.datetime) -> None:
        pairs = [self.entry(start)]
        await self.create(pairs, label="replay_base")
        await self.expect_counts(pairs[0][1], 0, {"organizer": 1, "room": 1}, label="replay_base_present")
        await self.replay_checks(start, pairs)

    async def replay_checks(self, start: dtm.datetime, pairs: list[tuple[Any, dict]]) -> None:
        entry, row = pairs[0]
        before = (row["uid"], row["outlook_booking_id"])
        await self.create([(entry.model_copy(), row)], label="same_operation_replay", allowed=[row])
        require(before == (row["uid"], row["outlook_booking_id"]), "Replay changed identity")
        # Race two first-time calls for one additional adjacent isolated operation.
        duplicate_entry, duplicate_row = self.entry(start + dtm.timedelta(minutes=8))
        require(await self.free(duplicate_entry.start, duplicate_entry.end), "Duplicate-call window occupied")
        duplicate_row["creation_started"] = True
        self.record("simultaneous_create_intent", operation=duplicate_row["operation_id"], calls=2)

        async def duplicate_call() -> Any:
            booking = await self.repository.create_booking(
                room=self.room,
                start=duplicate_entry.start,
                end=duplicate_entry.end,
                title=duplicate_entry.title,
                participant_emails=[],
                operation_id=duplicate_entry.operation_id,
            )
            self.remember(duplicate_row, booking)
            return booking

        results = await asyncio.gather(duplicate_call(), duplicate_call(), return_exceptions=True)
        identities = set()
        for result in results:
            if isinstance(result, BaseException):
                self.record("concurrent_error", error_type=type(result).__name__)
                raise AssertionError("Concurrent create failed") from result  # noqa: TRY004 — gathered failure, not a type error
            identities.add((result.uid, result.outlook_booking_id))
        require(len(identities) == 1, "Duplicate create identities")
        self.record("simultaneous_identity_equal", uid_token=identity_token(duplicate_row["uid"]))
        await self.expect_counts(duplicate_row, 0, {"organizer": 1, "room": 1}, label="simultaneous_single_copy")
        config = self.repository.account.protocol.config
        self.repository = type(self.repository)(
            self.repository.ews_endpoint, self.repository.account_email, config.credentials.password
        )
        self.record("fresh_repository_created")
        for _, row in [*pairs, (duplicate_entry, duplicate_row)]:
            old_identity = (row["uid"], row["outlook_booking_id"])
            result = await self.observe(row, label="restart_reconcile_no_write")
            require(
                result.organizer_presence == "present" and result.room_presence == "present", "Restart lost presence"
            )
            require(old_identity == (row["uid"], row["outlook_booking_id"]), "Restart changed identity")
            await self.expect_counts(row, 0, {"organizer": 1, "room": 1}, label="restart_single_copy")

    async def recurring(self, start: dtm.datetime) -> None:
        entry, row = self.entry(start, recurring=True)
        await self.create([(entry, row)], label="weekly_two_occurrences")
        for occurrence in range(2):
            await self.expect_counts(row, occurrence, {"organizer": 1, "room": 1}, label="recurrence_present")
        await self.cancel(row, occurrence=0, label="exact_first_occurrence")
        await self.expect_counts(row, 0, {"organizer": 0, "room": 0}, label="first_occurrence_removed")
        await self.expect_counts(row, 1, {"organizer": 1, "room": 1}, label="sibling_preserved")
        repeated = await self.cancel(row, occurrence=0, label="repeat_occurrence_cancellation")
        require(repeated.cancellation_status == "cancelled", "Repeated cancellation must be idempotent")
        await self.expect_counts(row, 1, {"organizer": 1, "room": 1}, label="sibling_still_preserved")

    async def overlap(self, start: dtm.datetime) -> None:
        first = self.entry(start)
        await self.create([first], label="overlap_base")
        await self.expect_counts(first[1], 0, {"organizer": 1, "room": 1}, label="base_present")
        second = self.entry(start + dtm.timedelta(minutes=1))
        await self.create([second], label="own_test_overlap", allowed=[first[1]])
        for attempt in range(4):
            for _, row in (first, second):
                result = await self.observe(row, label=f"overlap_observation_{attempt + 1}")
                require(result.organizer_presence == "present", "Overlap organizer item unexpectedly absent")
                self.record("overlap_actual_copies", uid_token=identity_token(row["uid"]), **await self.counts(row, 0))
            if attempt < 3:
                await asyncio.sleep(10)
        self.record("overlap_observed", policy_expectation="No automatic decline or acceptance assumed")


async def validate(start: dtm.datetime, journal: Path, scenario: str) -> int:
    # Library logs can include EWS payloads/server messages; only explicit redacted
    # evidence is printed. The private journal retains the IDs needed for cleanup.
    logging.disable(logging.CRITICAL)
    validation = LiveValidation(journal)
    passed = False
    try:
        start = await validation.select_start(start, recurring=scenario == "recurring")
        await getattr(validation, scenario)(start)
        passed = True
        validation.record("assertions_passed", scenario=scenario)
    except Exception as error:
        validation.record(
            "scenario_failed",
            scenario=scenario,
            error_type=type(error).__name__,
            assertion=str(error) if isinstance(error, AssertionError) else None,
        )
    finally:
        cleaned = await validation.cleanup()
    validation.record("finished", scenario=scenario, assertions_passed=passed, cleanup_verified=cleaned)
    return 0 if passed and cleaned else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=dtm.datetime.fromisoformat, required=True)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--scenario", choices=("batch", "replay", "recurring", "overlap"), required=True)
    parser.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args()
    if args.start.tzinfo is None:
        parser.error("Start must include a timezone")
    if args.journal.parent.resolve() != Path("/tmp"):
        parser.error("Use a new private journal directly in /tmp")
    start = args.start.astimezone(MSK)
    if not dtm.datetime.now(MSK) < start < dtm.datetime.now(MSK) + dtm.timedelta(days=7):
        parser.error("Test must be in the next seven days")
    return asyncio.run(validate(start, args.journal, args.scenario))


if __name__ == "__main__":
    raise SystemExit(main())
