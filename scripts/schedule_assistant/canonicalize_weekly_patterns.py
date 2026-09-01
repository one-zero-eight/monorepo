import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import CoursesConfig
from src.schedule_assistant.modules.schedule_config.weekly_pattern_canonicalization import (
    canonicalize_courses,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Canonicalize dense weekly-pattern edits without changing concrete meetings",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Without this flag the script only reports them.",
    )
    parser.add_argument(
        "--course",
        action="append",
        default=[],
        help="Only normalize this course name. May be specified multiple times.",
    )
    return parser.parse_args()


def run(*, apply: bool, course_names: set[str] | None) -> int:
    repository = ScheduleConfigRepository()
    term = repository.get_term()
    courses = repository.get_courses()
    normalized, stats = canonicalize_courses(
        courses.courses,
        term,
        course_names=course_names,
    )

    print(f"Courses changed: {stats.courses_changed}")
    print(f"Weekly slots changed: {stats.slots_changed}")
    print(f"Edits: {stats.edits_before} -> {stats.edits_after}")

    if stats.slots_changed == 0:
        print("Nothing to change.")
        return 0
    if not apply:
        print("Dry run complete. Run again with --apply to write changes.")
        return 0

    _, revision = repository.set_courses(
        CoursesConfig(courses=normalized),
        saved_by="script:canonicalize-weekly-patterns",
    )
    print(f"Saved revision: {revision}")
    return 0


def main() -> int:
    args = parse_args()
    return run(
        apply=args.apply,
        course_names=set(args.course) if args.course else None,
    )


if __name__ == "__main__":
    raise SystemExit(main())
