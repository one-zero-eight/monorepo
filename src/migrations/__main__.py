"""Run with ``uv run -m src.migrations <service>``."""

import argparse
import sys

from src.migrations import SERVICES, MigrationConfigurationError, migrate_service


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Apply pending database migrations for one configured service.")
    parser.add_argument("service", choices=SERVICES)
    args = parser.parse_args(argv)

    try:
        migrate_service(args.service)
    except MigrationConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 — CLI boundary must not expose credentials in exception messages.
        # Driver and settings errors can include passwords or full connection URIs.
        print(f"Migrations failed for {args.service} ({type(exc).__name__}).", file=sys.stderr)
        return 1

    print(f"Migrations completed for {args.service}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
