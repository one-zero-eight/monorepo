"""Add teaching blocks and course pool metadata without changing existing sessions.

Revision ID: p6j7k8l9m0n1
Revises: o5i6j7k8l9m0
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p6j7k8l9m0n1"
down_revision: str | None = "o5i6j7k8l9m0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("term", sa.Column("blocks", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    op.alter_column("term", "blocks", server_default=None)
    op.add_column("courses", sa.Column("blocks", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("courses", "blocks")
    op.drop_column("term", "blocks")
