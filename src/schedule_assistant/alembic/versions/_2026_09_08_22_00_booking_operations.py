"""Persist booking intents and cross-process reservations.

Revision ID: n4h5i6j7k8l9
Revises: m3g4h5i6j7k8
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "n4h5i6j7k8l9"
down_revision: str | None = "m3g4h5i6j7k8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "booking_operations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("reservation_key", sa.String(), nullable=True, unique=True),
        sa.Column("task_id", sa.String(), nullable=False),
        sa.Column("item", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_booking_operations_task_id", "booking_operations", ["task_id"])


def downgrade() -> None:
    op.drop_table("booking_operations")
