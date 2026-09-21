"""Drop irreversible schedule-config history snapshots and patches.

Revision ID: o5i6j7k8l9m0
Revises: n4h5i6j7k8l9
"""

from collections.abc import Sequence

from alembic import op

revision: str = "o5i6j7k8l9m0"
down_revision: str | None = "n4h5i6j7k8l9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("config_history_events")


def downgrade() -> None:
    raise NotImplementedError(
        "Cannot restore config_history_events: dropped snapshots and patches are irreversible. "
        "Recover from a verified backup if historical configuration data is required."
    )
