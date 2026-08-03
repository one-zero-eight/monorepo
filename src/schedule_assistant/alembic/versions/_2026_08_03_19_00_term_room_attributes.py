"""add room_attributes to term

Revision ID: f6a7b8c9d0e2
Revises: e5f6a7b8c9d0
Create Date: 2026-08-03 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6a7b8c9d0e2"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "term",
        sa.Column(
            "room_attributes",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
    )
    op.alter_column("term", "room_attributes", server_default=None)


def downgrade() -> None:
    op.drop_column("term", "room_attributes")
