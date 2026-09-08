"""Offline, dry-run-first Fall 2026 teaching-window and Auto-series repair report.

Input is a ScheduleConfig JSON export and an explicit section/program -> year
selection, e.g. {"core/BS_Y3_EN": 3, "electives/BS_Y3_EN": 3}. No database or
Exchange clients are constructed. --write-config only writes a NEW local export,
after comparing --approved-report with a fresh dry run; it never applies Exchange
changes. An Auto-booking export may be supplied for excess-occurrence reporting.
"""

import argparse
import datetime as dtm
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.schedule_assistant.modules.bookings.match import (
    booking_coverage,
    extra_booking_candidate_key,
    is_schedule_assistant_auto_title,
    iter_booking_occurrences,
)
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.schedule_config.schemas import (
    CoursesConfig,
    ScheduleConfig,
    SectionsConfig,
    TermConfig,
)
from src.schedule_assistant.modules.schedule_config.semester_windows import union_semester_window

# This is the reviewed one-time migration data, not a business-logic default.
FALL_2026_TEACHING_WINDOWS = {
    1: ("2026-09-01", "2026-12-15"),
    2: ("2026-08-31", "2026-12-14"),
    3: ("2026-08-24", "2026-12-07"),
}


def prepare_repair(
    config: ScheduleConfig,
    selection: dict[str, int],
    auto_bookings: list[dict[str, Any]],
) -> tuple[ScheduleConfig, dict[str, Any]]:
    if not selection:
        raise ValueError("Explicit section/program selection is required")
    if config.term.semester.start_date.year != 2026 or config.term.semester.end_date.year != 2026:
        raise ValueError("This migration only supports Fall 2026")
    revised = config.model_copy(deep=True)
    old_window = union_semester_window(config.term)
    programs = {
        f"{section.code}/{program.code}": program for section in revised.term.sections for program in section.programs
    }
    unknown = selection.keys() - programs.keys()
    if unknown:
        raise ValueError(f"Unknown section/program selection: {sorted(unknown)}")
    changes = []
    for key, year in sorted(selection.items()):
        if type(year) is not int or year not in FALL_2026_TEACHING_WINDOWS:
            raise ValueError(f"Unsupported study year for {key}: {year}")
        program = programs[key]
        start, end = FALL_2026_TEACHING_WINDOWS[year]
        window = TermConfig.DateRange(start_date=dtm.date.fromisoformat(start), end_date=dtm.date.fromisoformat(end))
        changes.append(
            {
                "program": key,
                "year": year,
                "before": (program.semester or config.term.semester).model_dump(mode="json"),
                "after": window.model_dump(mode="json"),
                "selectors": [f"@{program.code}", *[f"@{program.code}/{track.code}" for track in program.tracks]],
            }
        )
        program.semester = window
    sections = SectionsConfig(sections=revised.term.sections, students_groups=revised.students_groups)
    slots = build_bookable_slots(
        CoursesConfig(courses=revised.courses),
        sections,
        revised.term,
        known_room_ids={room.id for room in revised.rooms},
    )
    series = []
    for booking in auto_bookings:
        actual = set(iter_booking_occurrences(booking))
        candidates = [slot for slot in slots if booking_coverage(slot.payload, [booking]).bookings]
        expected = {
            occurrence for slot in candidates for occurrence in booking_coverage(slot.payload, [booking]).expected
        }
        retained = actual & expected
        excess = actual - expected
        managed = bool(booking.get("outlook_booking_id") and booking.get("organizer_mailbox") and booking.get("uid"))
        auto = is_schedule_assistant_auto_title(str(booking.get("title") or ""))
        complete = booking.get("recurrence_complete", not bool(booking.get("recurrence"))) and bool(actual)
        component_ids = {slot.component_id for slot in candidates}
        action = "keep" if not excess else "review_excess"
        if not auto or not managed or not complete or len(component_ids) != 1:
            action = "manual_review"
        elif excess and retained:
            action = (
                "propose_shorten"
                if min(start for start, _ in excess) > max(start for start, _ in retained)
                else "review_exceptions"
            )
        series.append(
            {
                "identity": extra_booking_candidate_key(booking),
                "uid": booking.get("uid"),
                "organizer_mailbox": booking.get("organizer_mailbox"),
                "action": action,
                "retained_dates": sorted({start.date().isoformat() for start, _ in retained}),
                "excess_dates": sorted({start.date().isoformat() for start, _ in excess}),
                "proposed_until": max((start.date().isoformat() for start, _ in retained), default=None),
                "requires_exchange_validation": bool(excess),
                "can_apply": False,
            }
        )
    report = {
        "dry_run": True,
        "config_sha256": hashlib.sha256(config.model_dump_json().encode()).hexdigest(),
        "selection": selection,
        "program_changes": changes,
        # Preserve the old range even after the revised config is exported.
        "diagnostic_scan_window": old_window.model_dump(mode="json"),
        "booking_export_completeness": "not_verified; targeted organizer and room reads required",
        "unselected_programs": sorted(programs.keys() - selection.keys()),
        "series": series,
    }
    return revised, report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="ScheduleConfig JSON export (read only)")
    parser.add_argument(
        "--selection", type=Path, required=True, help="Reviewed JSON section/program -> study year mapping"
    )
    parser.add_argument("--auto-bookings", type=Path, help="Read-only Auto-booking JSON export")
    parser.add_argument("--approved-report", type=Path, help="Previously reviewed dry-run JSON report")
    parser.add_argument(
        "--write-config", type=Path, help="Write NEW corrected local JSON export; never writes DB/Exchange"
    )
    args = parser.parse_args()
    config = ScheduleConfig.model_validate_json(args.config.read_text())
    selection = json.loads(args.selection.read_text())
    bookings = json.loads(args.auto_bookings.read_text()) if args.auto_bookings else []
    revised, report = prepare_repair(config, selection, bookings)
    if args.write_config:
        if not args.approved_report or json.loads(args.approved_report.read_text()) != report:
            parser.error("--write-config requires an unchanged, reviewed --approved-report")
        with args.write_config.open("x") as output:
            output.write(revised.model_dump_json(indent=2) + "\n")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
