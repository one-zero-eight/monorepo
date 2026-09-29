"""rename workshops_hidden to events_hidden

Revision ID: bcf54d8acd7c
Revises: 5ce5340dc3cb
Create Date: 2026-09-30 02:28:11.889667

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bcf54d8acd7c"
down_revision: str | None = "5ce5340dc3cb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("users", "workshops_hidden", new_column_name="events_hidden")


def downgrade() -> None:
    op.alter_column("users", "events_hidden", new_column_name="workshops_hidden")
