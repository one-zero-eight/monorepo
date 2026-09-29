"""rename events calendar access key paths

Revision ID: d8f66b4e2a13
Revises: bcf54d8acd7c

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f66b4e2a13"
down_revision: str | None = "bcf54d8acd7c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE user_schedule_keys "
            "SET resource_path = '/users/' || user_id || '/events.ics' "
            "WHERE resource_path = '/users/' || user_id || '/workshops.ics'"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE user_schedule_keys "
            "SET resource_path = '/users/' || user_id || '/workshops.ics' "
            "WHERE resource_path = '/users/' || user_id || '/events.ics'"
        )
    )
