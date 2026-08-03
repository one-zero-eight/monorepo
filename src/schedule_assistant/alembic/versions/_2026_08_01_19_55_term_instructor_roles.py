"""add term.instructor_roles

Revision ID: b2c3d4e5f6a7
Revises: d4e5f6a7b8c9
Create Date: 2026-08-01 19:55:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "term",
        sa.Column(
            "instructor_roles",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("term", "instructor_roles", server_default=None)


def downgrade() -> None:
    op.drop_column("term", "instructor_roles")
