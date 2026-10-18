"""Add timer invitations and the invite permission.

Revision ID: 8f3c21ad7e60
Revises: e47b1a90c623
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f3c21ad7e60"
down_revision: str | None = "e47b1a90c623"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The new enum value is used by the application only after this migration commits.
    op.execute("ALTER TYPE timer_permission ADD VALUE 'invite'")
    op.create_table(
        "invitations",
        sa.Column("uuid", sa.Uuid(), nullable=False),
        sa.Column("timer_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("uuid"),
        sa.ForeignKeyConstraint(["timer_id"], ["timers.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_invitations_timer_id", "invitations", ["timer_id"])


def downgrade() -> None:
    raise RuntimeError("Removing invitations and invite permission requires a reviewed forward migration")
