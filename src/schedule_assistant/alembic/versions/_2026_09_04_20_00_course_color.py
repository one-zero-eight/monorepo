"""add optional course color

Revision ID: m3g4h5i6j7k8
Revises: l2f3a4b5c6d7
Create Date: 2026-09-04 20:00:00.000000

"""

import json
import re
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "m3g4h5i6j7k8"
down_revision: str | None = "l2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_COURSE_COLOR_PATH = re.compile(r"^/courses/\d+/color$")
_COURSE_PATH = re.compile(r"^/courses/\d+$")


def _without_course_color(course: Any) -> Any:
    if not isinstance(course, dict):
        return course
    cleaned = dict(course)
    cleaned.pop("color", None)
    return cleaned


def _rewrite_snapshot(snapshot: Any) -> Any:
    if not isinstance(snapshot, dict):
        return snapshot
    cleaned = dict(snapshot)
    courses = cleaned.get("courses")
    if isinstance(courses, list):
        cleaned["courses"] = [_without_course_color(course) for course in courses]
    return cleaned


def _rewrite_patch_value(path: str, value: Any) -> Any:
    if not path:
        return _rewrite_snapshot(value)
    if path == "/courses" and isinstance(value, list):
        return [_without_course_color(course) for course in value]
    if _COURSE_PATH.fullmatch(path):
        return _without_course_color(value)
    return value


def _rewrite_patch(patch: Any) -> Any:
    if not isinstance(patch, list):
        return patch
    rewritten: list[Any] = []
    for operation in patch:
        if not isinstance(operation, dict):
            rewritten.append(operation)
            continue
        path = operation.get("path")
        source = operation.get("from")
        if isinstance(path, str) and _COURSE_COLOR_PATH.fullmatch(path):
            continue
        if isinstance(source, str) and _COURSE_COLOR_PATH.fullmatch(source):
            continue
        item = dict(operation)
        if isinstance(path, str) and "value" in item:
            item["value"] = _rewrite_patch_value(path, item["value"])
        rewritten.append(item)
    return rewritten


def _json_param(value: Any) -> str:
    return json.dumps(value)


def upgrade() -> None:
    op.add_column("courses", sa.Column("color", sa.String(length=7), nullable=True))


def downgrade() -> None:
    connection = op.get_bind()
    events = connection.execute(sa.text("SELECT id, snapshot, patch FROM config_history_events")).mappings().all()
    for event in events:
        connection.execute(
            sa.text(
                "UPDATE config_history_events "
                "SET snapshot = CAST(:snapshot AS json), patch = CAST(:patch AS json) "
                "WHERE id = :id"
            ),
            {
                "snapshot": _json_param(_rewrite_snapshot(event.get("snapshot"))),
                "patch": _json_param(_rewrite_patch(event.get("patch"))),
                "id": event["id"],
            },
        )
    op.drop_column("courses", "color")
