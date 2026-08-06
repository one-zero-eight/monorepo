"""add distribution_uploads table

Revision ID: h8b9c0d1e2f3
Revises: g7a8b9c0d1e2
Create Date: 2026-08-06 12:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "h8b9c0d1e2f3"
down_revision: str | None = "g7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "distribution_uploads",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("section_code", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("file_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_by", sa.String(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sheet_name", sa.String(), nullable=True),
        sa.Column("email_column", sa.String(), nullable=True),
        sa.Column("membership_columns", sa.JSON(), nullable=False),
        sa.Column("mapping", sa.JSON(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("updated_groups", sa.JSON(), nullable=False),
        sa.Column("skipped_labels", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_distribution_uploads_section_code",
        "distribution_uploads",
        ["section_code"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_distribution_uploads_section_code", table_name="distribution_uploads")
    op.drop_table("distribution_uploads")
