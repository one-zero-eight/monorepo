"""rename component student_groups to audience and session occurrences to dates_pattern

Revision ID: k1e2f3a4b5c6
Revises: j0d1e2f3a4b5
Create Date: 2026-08-21 13:00:00.000000

"""

import json
import re
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "k1e2f3a4b5c6"
down_revision: str | None = "j0d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_session_keys(session: dict[str, Any], *, forward: bool) -> dict[str, Any]:
    if forward:
        old, new = "occurrences", "dates_pattern"
    else:
        old, new = "dates_pattern", "occurrences"
    if old in session and new not in session:
        session[new] = session.pop(old)
    elif old in session:
        session.pop(old)
    return session


def _rename_component_keys(component: dict[str, Any], *, forward: bool) -> dict[str, Any]:
    if forward:
        old, new = "student_groups", "audience"
    else:
        old, new = "audience", "student_groups"
    if old in component and new not in component:
        component[new] = component.pop(old)
    elif old in component:
        component.pop(old)

    sessions = component.get("sessions")
    if isinstance(sessions, list):
        for session in sessions:
            if isinstance(session, dict):
                _rename_session_keys(session, forward=forward)
    return component


def _rewrite_components(components: Any, *, forward: bool) -> Any:
    if not isinstance(components, list):
        return components
    return [
        _rename_component_keys(dict(component), forward=forward) if isinstance(component, dict) else component
        for component in components
    ]


def _rewrite_schedule_dump(payload: Any, *, forward: bool) -> Any:
    if not isinstance(payload, dict):
        return payload
    courses = payload.get("courses")
    if not isinstance(courses, list):
        return payload
    for course in courses:
        if isinstance(course, dict) and "components" in course:
            course["components"] = _rewrite_components(course.get("components"), forward=forward)
    return payload


def _rewrite_json_patch_path(path: str, *, forward: bool) -> str:
    if forward:
        path = re.sub(r"(/components/\d+)/student_groups\b", r"\1/audience", path)
        path = re.sub(r"(/sessions/\d+)/occurrences\b", r"\1/dates_pattern", path)
    else:
        path = re.sub(r"(/components/\d+)/audience\b", r"\1/student_groups", path)
        path = re.sub(r"(/sessions/\d+)/dates_pattern\b", r"\1/occurrences", path)
    return path


def _rewrite_patch_value(value: Any, *, forward: bool) -> Any:
    if isinstance(value, dict):
        if "tag" in value and ("student_groups" in value or "audience" in value or "sessions" in value):
            return _rename_component_keys(dict(value), forward=forward)
        if ("occurrences" in value or "dates_pattern" in value) and "tag" not in value:
            return _rename_session_keys(dict(value), forward=forward)
        if "courses" in value:
            return _rewrite_schedule_dump(dict(value), forward=forward)
        if "components" in value and isinstance(value.get("components"), list):
            course = dict(value)
            course["components"] = _rewrite_components(course.get("components"), forward=forward)
            return course
        return {key: _rewrite_patch_value(item, forward=forward) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_patch_value(item, forward=forward) for item in value]
    return value


def _rewrite_patch_ops(patch: Any, *, forward: bool) -> Any:
    if not isinstance(patch, list):
        return patch
    rewritten: list[Any] = []
    for op_item in patch:
        if not isinstance(op_item, dict):
            rewritten.append(op_item)
            continue
        item = dict(op_item)
        if isinstance(item.get("path"), str):
            item["path"] = _rewrite_json_patch_path(item["path"], forward=forward)
        if isinstance(item.get("from"), str):
            item["from"] = _rewrite_json_patch_path(item["from"], forward=forward)
        if "value" in item:
            item["value"] = _rewrite_patch_value(item["value"], forward=forward)
        rewritten.append(item)
    return rewritten


def _json_param(value: Any) -> str:
    return json.dumps(value)


def upgrade() -> None:
    connection = op.get_bind()

    courses = connection.execute(sa.text("SELECT name, components FROM courses")).mappings().all()
    for course in courses:
        components = _rewrite_components(course.get("components"), forward=True)
        connection.execute(
            sa.text("UPDATE courses SET components = CAST(:components AS json) WHERE name = :name"),
            {"components": _json_param(components), "name": course["name"]},
        )

    events = connection.execute(sa.text("SELECT id, snapshot, patch FROM config_history_events")).mappings().all()
    for event in events:
        snapshot = event.get("snapshot") if isinstance(event.get("snapshot"), dict) else {}
        snapshot = _rewrite_schedule_dump(snapshot, forward=True)
        patch = _rewrite_patch_ops(event.get("patch"), forward=True)
        connection.execute(
            sa.text(
                "UPDATE config_history_events SET snapshot = CAST(:snapshot AS json), patch = CAST(:patch AS json) WHERE id = :id"
            ),
            {"snapshot": _json_param(snapshot), "patch": _json_param(patch), "id": event["id"]},
        )


def downgrade() -> None:
    connection = op.get_bind()

    courses = connection.execute(sa.text("SELECT name, components FROM courses")).mappings().all()
    for course in courses:
        components = _rewrite_components(course.get("components"), forward=False)
        connection.execute(
            sa.text("UPDATE courses SET components = CAST(:components AS json) WHERE name = :name"),
            {"components": _json_param(components), "name": course["name"]},
        )

    events = connection.execute(sa.text("SELECT id, snapshot, patch FROM config_history_events")).mappings().all()
    for event in events:
        snapshot = event.get("snapshot") if isinstance(event.get("snapshot"), dict) else {}
        snapshot = _rewrite_schedule_dump(snapshot, forward=False)
        patch = _rewrite_patch_ops(event.get("patch"), forward=False)
        connection.execute(
            sa.text(
                "UPDATE config_history_events SET snapshot = CAST(:snapshot AS json), patch = CAST(:patch AS json) WHERE id = :id"
            ),
            {"snapshot": _json_param(snapshot), "patch": _json_param(patch), "id": event["id"]},
        )
