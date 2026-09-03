"""remove student group kind

Revision ID: l2f3a4b5c6d7
Revises: k1e2f3a4b5c6
Create Date: 2026-09-03 09:00:00.000000

"""

import json
import re
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "l2f3a4b5c6d7"
down_revision: str | None = "k1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GROUP_KIND_PATH = re.compile(r"^/students_groups/\d+/kind$")
_GROUP_PATH = re.compile(r"^/students_groups/\d+$")


def _without_group_kind(group: Any) -> Any:
    if not isinstance(group, dict):
        return group
    cleaned = dict(group)
    cleaned.pop("kind", None)
    return cleaned


def _rewrite_snapshot(snapshot: Any) -> Any:
    if not isinstance(snapshot, dict):
        return snapshot
    cleaned = dict(snapshot)
    groups = cleaned.get("students_groups")
    if isinstance(groups, list):
        cleaned["students_groups"] = [_without_group_kind(group) for group in groups]
    return cleaned


def _restore_snapshot_group_kinds(snapshot: Any) -> Any:
    if not isinstance(snapshot, dict):
        return snapshot
    restored = dict(snapshot)
    term = restored.get("term")
    sections = term.get("sections") if isinstance(term, dict) else None
    memberships = _group_sections(sections)
    groups = restored.get("students_groups")
    if not isinstance(groups, list):
        return restored
    restored_groups: list[Any] = []
    ambiguous: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            restored_groups.append(group)
            continue
        item = dict(group)
        code = str(item.get("code") or "").strip()
        section_codes = memberships.get(code, set())
        if len(section_codes) != 1:
            ambiguous.append(f"{code!r} -> {sorted(section_codes)}")
            continue
        section_code = next(iter(section_codes))
        item["kind"] = "elective" if section_code == "electives" else section_code
        restored_groups.append(item)
    if ambiguous:
        raise RuntimeError(
            "Cannot restore student group kind in config history; each group must belong to exactly one section: "
            + "; ".join(ambiguous)
        )
    restored["students_groups"] = restored_groups
    return restored


def _rewrite_patch_value(path: str, value: Any) -> Any:
    if not path:
        return _rewrite_snapshot(value)
    if path == "/students_groups" and isinstance(value, list):
        return [_without_group_kind(group) for group in value]
    if _GROUP_PATH.fullmatch(path):
        return _without_group_kind(value)
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
        if isinstance(path, str) and _GROUP_KIND_PATH.fullmatch(path):
            continue
        if isinstance(source, str) and _GROUP_KIND_PATH.fullmatch(source):
            continue
        item = dict(operation)
        if isinstance(path, str) and "value" in item:
            item["value"] = _rewrite_patch_value(path, item["value"])
        rewritten.append(item)
    return rewritten


def _json_param(value: Any) -> str:
    return json.dumps(value)


def _group_sections(sections: Any) -> dict[str, set[str]]:
    memberships: dict[str, set[str]] = {}
    if not isinstance(sections, list):
        return memberships
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_code = str(section.get("code") or "").strip()
        if not section_code:
            continue
        for program in section.get("programs") or []:
            if not isinstance(program, dict):
                continue
            group_lists = [program.get("groups") or []]
            group_lists.extend(
                track.get("groups") or [] for track in program.get("tracks") or [] if isinstance(track, dict)
            )
            for groups in group_lists:
                for group_code in groups:
                    code = str(group_code or "").strip()
                    if code:
                        memberships.setdefault(code, set()).add(section_code)
    return memberships


def upgrade() -> None:
    connection = op.get_bind()
    events = connection.execute(sa.text("SELECT id, snapshot, patch FROM config_history_events")).mappings().all()
    for event in events:
        snapshot = _rewrite_snapshot(event.get("snapshot"))
        patch = _rewrite_patch(event.get("patch"))
        connection.execute(
            sa.text(
                "UPDATE config_history_events "
                "SET snapshot = CAST(:snapshot AS json), patch = CAST(:patch AS json) "
                "WHERE id = :id"
            ),
            {
                "snapshot": _json_param(snapshot),
                "patch": _json_param(patch),
                "id": event["id"],
            },
        )
    op.drop_column("student_groups", "kind")


def downgrade() -> None:
    op.add_column("student_groups", sa.Column("kind", sa.String(), nullable=True))
    connection = op.get_bind()
    term = connection.execute(sa.text("SELECT sections FROM term LIMIT 1")).mappings().first()
    memberships = _group_sections((term or {}).get("sections"))
    ambiguous: list[str] = []
    for row in connection.execute(sa.text("SELECT code FROM student_groups")).mappings():
        sections = memberships.get(row["code"], set())
        if len(sections) != 1:
            ambiguous.append(f"{row['code']!r} -> {sorted(sections)}")
            continue
        section_code = next(iter(sections))
        kind = "elective" if section_code == "electives" else section_code
        connection.execute(
            sa.text("UPDATE student_groups SET kind = :kind WHERE code = :code"),
            {"kind": kind, "code": row["code"]},
        )
    if ambiguous:
        raise RuntimeError(
            "Cannot restore student_groups.kind; each group must belong to exactly one section: " + "; ".join(ambiguous)
        )
    op.alter_column("student_groups", "kind", existing_type=sa.String(), nullable=False)

    events = connection.execute(sa.text("SELECT id, snapshot FROM config_history_events")).mappings().all()
    for event in events:
        snapshot = _restore_snapshot_group_kinds(event.get("snapshot"))
        connection.execute(
            sa.text("UPDATE config_history_events SET snapshot = CAST(:snapshot AS json) WHERE id = :id"),
            {"snapshot": _json_param(snapshot), "id": event["id"]},
        )
