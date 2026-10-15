"""Export local service contracts without running lifespan, databases, or network calls."""

import argparse
import importlib
import json
import os
from pathlib import Path

SERVICES = ("clubs", "events", "room_booking", "schedule_assistant")


def export_schema(service: str) -> str:
    # Codegen uses public placeholder settings, never developer credentials.
    os.environ["SETTINGS_PATH"] = str(Path(__file__).absolute().parent.parent / "settings.example.yaml")
    app = importlib.import_module(f"src.{service}.app").app
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("service", choices=SERVICES)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(export_schema(args.service), encoding="utf-8")


if __name__ == "__main__":
    main()
