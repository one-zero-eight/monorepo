"""drop course_tags from courses

Revision ID: e5f6a7b8c9d0
Revises: a7b8c9d0e1f2
Create Date: 2026-08-03 17:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("courses", "course_tags")


def downgrade() -> None:
    op.add_column(
        "courses",
        sa.Column(
            "course_tags",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("courses", "course_tags", server_default=None)
