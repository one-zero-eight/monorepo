"""initial schedule assistant schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-07-09 18:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "term",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("semester_start", sa.Date(), nullable=False),
        sa.Column("semester_end", sa.Date(), nullable=False),
        sa.Column("days", sa.JSON(), nullable=False),
        sa.Column("starting_day", sa.String(), nullable=False),
        sa.Column("time_slots", sa.JSON(), nullable=False),
        sa.Column("sections", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "student_groups",
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("estimated_size", sa.Integer(), nullable=True),
        sa.Column("students", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_table(
        "courses",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("short_name", sa.String(), nullable=True),
        sa.Column("name_ru", sa.String(), nullable=True),
        sa.Column("short_name_ru", sa.String(), nullable=True),
        sa.Column("course_tags", sa.JSON(), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("name"),
    )
    op.create_table(
        "instructors",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name_en", sa.String(), nullable=True),
        sa.Column("name_ru", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("alias", sa.String(), nullable=True),
        sa.Column("position", sa.String(), nullable=True),
        sa.Column("slot_preferences", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "config_meta",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "config_history_events",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("resources", sa.JSON(), nullable=False),
        sa.Column("saved_at", sa.String(), nullable=False),
        sa.Column("saved_by", sa.String(), nullable=False),
        sa.Column("patch", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("config_history_events")
    op.drop_table("config_meta")
    op.drop_table("rooms")
    op.drop_table("instructors")
    op.drop_table("courses")
    op.drop_table("student_groups")
    op.drop_table("term")
