"""add courses.section_code

Revision ID: i9c0d1e2f3a4
Revises: h8b9c0d1e2f3
Create Date: 2026-08-13 21:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "i9c0d1e2f3a4"
down_revision: str | None = "h8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("courses", sa.Column("section_code", sa.String(), nullable=True))

    connection = op.get_bind()
    term_row = connection.execute(sa.text("SELECT sections FROM term LIMIT 1")).mappings().first()
    sections = list((term_row or {}).get("sections") or [])

    group_to_section: dict[str, str] = {}
    program_to_section: dict[str, str] = {}
    for section in sections:
        section_code = str(section.get("code") or "").strip()
        if not section_code:
            continue
        for program in section.get("programs") or []:
            program_code = str(program.get("code") or "").strip()
            if program_code:
                program_to_section[program_code] = section_code
            for group_id in program.get("groups") or []:
                gid = str(group_id or "").strip()
                if gid:
                    group_to_section[gid] = section_code
            for track in program.get("tracks") or []:
                for group_id in track.get("groups") or []:
                    gid = str(group_id or "").strip()
                    if gid:
                        group_to_section[gid] = section_code

    courses = connection.execute(sa.text("SELECT name, components FROM courses")).mappings().all()
    ambiguous: list[str] = []
    for course in courses:
        codes: set[str] = set()
        for component in course.get("components") or []:
            tokens = list(component.get("student_groups") or [])
            for session in component.get("sessions") or []:
                tokens.extend(session.get("audience") or [])
            for token in tokens:
                raw = str(token or "").strip()
                if not raw:
                    continue
                if raw.startswith("@"):
                    body = raw[1:]
                    program_code = body.split("/", 1)[0].strip()
                    section_code = program_to_section.get(program_code)
                    if section_code:
                        codes.add(section_code)
                    continue
                section_code = group_to_section.get(raw)
                if section_code:
                    codes.add(section_code)
        if len(codes) != 1:
            ambiguous.append(f"{course['name']!r} -> {sorted(codes)}")
            continue
        connection.execute(
            sa.text("UPDATE courses SET section_code = :section_code WHERE name = :name"),
            {"section_code": next(iter(codes)), "name": course["name"]},
        )

    if ambiguous:
        raise RuntimeError(
            "Cannot backfill courses.section_code; each course must map to exactly one section: " + "; ".join(ambiguous)
        )

    remaining = connection.execute(
        sa.text("SELECT name FROM courses WHERE section_code IS NULL OR section_code = ''")
    ).fetchall()
    if remaining:
        names = ", ".join(repr(row[0]) for row in remaining)
        raise RuntimeError(f"courses.section_code still empty for: {names}")

    op.alter_column("courses", "section_code", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    op.drop_column("courses", "section_code")
