"""drop unused events tables

Revision ID: a1c4e8f9b203
Revises: f3b9a7c2e614

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1c4e8f9b203"
down_revision: str | None = "f3b9a7c2e614"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("events_x_event_groups", if_exists=True)
    op.drop_table("event_patches", if_exists=True)
    op.drop_table("events", if_exists=True)


def downgrade() -> None:
    raise RuntimeError("Event data was deleted; restore a database backup to roll back this migration")
