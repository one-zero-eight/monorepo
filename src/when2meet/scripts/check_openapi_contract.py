import difflib
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))


def canonical_json(data) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> int:
    from src.when2meet.app import app

    contract_path = Path(__file__).resolve().parents[1] / "api" / "openapi.yaml"
    committed_schema = yaml.safe_load(contract_path.read_text())
    generated_schema = app.openapi()

    committed_json = canonical_json(committed_schema)
    generated_json = canonical_json(generated_schema)

    if committed_json == generated_json:
        print(f"{contract_path} matches the generated When2Meet OpenAPI schema.")
        return 0

    diff = difflib.unified_diff(
        committed_json.splitlines(keepends=True),
        generated_json.splitlines(keepends=True),
        fromfile=str(contract_path),
        tofile="generated when2meet openapi schema",
    )
    print("When2Meet OpenAPI contract is out of date. Regenerate src/when2meet/api/openapi.yaml.")
    print("".join(diff))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
