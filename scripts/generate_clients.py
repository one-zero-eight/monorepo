"""Generate committed clients without storing OpenAPI schemas in git.

By default --check verifies local services offline. Explicit --service selections
also allow checking external clients against the current upstream contracts.
"""

import argparse
import json
import os
import subprocess  # noqa: S404 — isolates service imports during local code generation
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import httpx
from httpxgen.generator import GenerationError
from httpxgen.io import filter_operations_by_tags, write_client
from httpxgen.openapi import OpenAPISpec

from scripts.export_openapi import SERVICES

ROOT = Path(__file__).absolute().parent.parent
CLIENTS = {
    "clubs": "ClubsClient",
    "events": "EventsClient",
    "room_booking": "RoomBookingClient",
    "schedule_assistant": "ScheduleAssistantClient",
    "music_room": "MusicRoomClient",
    "sport_v3": "SportV3Client",
}
EXTERNAL_SCHEMAS = {
    "music_room": "https://api.innohassle.ru/music-room/v0/openapi.json",
    "sport_v3": "https://sport.innopolis.university/api/v3/openapi.json",
}


def load_schema(service: str) -> dict[str, Any]:
    if service in EXTERNAL_SCHEMAS:
        response = httpx.get(EXTERNAL_SCHEMAS[service], timeout=60, follow_redirects=True)
        response.raise_for_status()
        return response.json()
    # Separate processes keep service imports and OpenAPI registries isolated.
    with TemporaryDirectory() as temporary:
        exported = Path(temporary) / "openapi.json"
        subprocess.run(  # noqa: S603 — executable and module are fixed; service is from CLIENTS
            [sys.executable, "-m", "scripts.export_openapi", service, str(exported)],
            cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": "0"},
            check=True,
        )
        return json.loads(exported.read_text(encoding="utf-8"))


def client_schema(service: str, spec: dict[str, Any]) -> OpenAPISpec:
    if service == "clubs":
        # Unused image redirects have no 2xx response; generate the consumed API only.
        spec["paths"] = {
            path: {"get": spec["paths"][path]["get"]}
            for path in ("/clubs/", "/clubs/by-id/{id}", "/clubs/owned-by/{innohassle_id}")
        }
    elif service == "music_room":
        # Upstream omits the binary response annotation for its generated PNG.
        operation = spec["paths"]["/bookings/form_schedule"]["get"]
        operation["responses"]["200"]["content"]["image/png"]["schema"] = {"type": "string", "format": "binary"}
        # A named date reference avoids generated parameter/type shadowing,
        # without changing the wire format or editing generated packages.
        spec["components"]["schemas"]["CalendarDate"] = {"type": "string", "format": "date"}
        for path in ("/users/me/remaining_daily_hours", "/users/me/remaining_weekly_hours"):
            for parameter in spec["paths"][path]["get"]["parameters"]:
                if parameter["name"] == "date":
                    parameter["schema"]["anyOf"] = [{"$ref": "#/components/schemas/CalendarDate"}, {"type": "null"}]
    parsed = OpenAPISpec.model_validate(spec)
    if service in {"clubs", "schedule_assistant"}:
        # Keep only reachable schemas, avoiding unrelated date-field collisions.
        tag = "Clubs" if service == "clubs" else "Schedule Integration"
        parsed = filter_operations_by_tags(parsed, [tag])
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--service", choices=CLIENTS, action="append")
    args = parser.parse_args()
    services = args.service or (SERVICES if args.check else CLIENTS)
    failed = False
    for service in services:
        try:
            write_client(
                spec=client_schema(service, load_schema(service)),
                package_dir=ROOT / "src" / "clients" / service,
                package_name=f"src.clients.{service}",
                client_name=CLIENTS[service],
                http_client="httpx",
                check=args.check,
            )
        except (GenerationError, ValueError, httpx.HTTPError) as error:
            print(f"{service}: {error}", file=sys.stderr)
            failed = True
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
