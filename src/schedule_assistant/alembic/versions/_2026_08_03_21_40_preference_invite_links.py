"""add preference_invite_links table

Revision ID: a1b2c3d4e5f6
Revises: f6a7b8c9d0e2
Create Date: 2026-08-03 21:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "g7a8b9c0d1e2"
down_revision: str | None = "f6a7b8c9d0e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "preference_invite_links",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("instructor_id", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_index(
        "ix_preference_invite_links_instructor_id",
        "preference_invite_links",
        ["instructor_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preference_invite_links_instructor_id",
        table_name="preference_invite_links",
    )
    op.drop_table("preference_invite_links")
