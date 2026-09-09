"""Export the application OpenAPI contract without starting its lifespan or database."""

import argparse
import json
from pathlib import Path

from src.schedule_assistant.app import app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
