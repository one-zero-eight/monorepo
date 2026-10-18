"""Replace the checkpoint table with an empty JSONB column.

Revision ID: e47b1a90c623
Revises: 0b674e5c891a
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e47b1a90c623"
down_revision: str | None = "0b674e5c891a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "timers", sa.Column("checkpoints", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False)
    )
    op.create_check_constraint("ck_timers_checkpoints_array", "timers", "jsonb_typeof(checkpoints) = 'array'")
    op.drop_table("timer_checkpoints")


def downgrade() -> None:
    raise RuntimeError("Restoring checkpoint tables requires a reviewed forward migration")
