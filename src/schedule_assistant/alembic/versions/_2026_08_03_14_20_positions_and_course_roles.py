"""rename instructor_roles to instructor_positions; add course roles

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-08-03 14:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "term",
        "instructor_roles",
        new_column_name="instructor_positions",
        existing_type=sa.JSON(),
        existing_nullable=False,
    )
    op.add_column(
        "term",
        sa.Column(
            "course_instructor_roles",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("term", "course_instructor_roles", server_default=None)
    op.add_column(
        "courses",
        sa.Column(
            "instructors",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("courses", "instructors", server_default=None)


def downgrade() -> None:
    op.drop_column("courses", "instructors")
    op.drop_column("term", "course_instructor_roles")
    op.alter_column(
        "term",
        "instructor_positions",
        new_column_name="instructor_roles",
        existing_type=sa.JSON(),
        existing_nullable=False,
    )
