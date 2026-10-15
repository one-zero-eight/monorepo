"""drop unused ownership tables

Revision ID: f3b9a7c2e614
Revises: d8f66b4e2a13

"""

from collections.abc import Sequence

from alembic import op

revision: str = "f3b9a7c2e614"
down_revision: str | None = "d8f66b4e2a13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("event_groups_x_ownerships", if_exists=True)
    op.drop_table("events_x_ownerships", if_exists=True)
    op.drop_table("tags_x_ownerships", if_exists=True)


def downgrade() -> None:
    raise RuntimeError("Ownership data was deleted; restore a database backup to roll back this migration")
