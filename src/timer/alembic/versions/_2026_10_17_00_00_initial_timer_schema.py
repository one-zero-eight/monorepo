"""Create timer storage.

Revision ID: 0b674e5c891a
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0b674e5c891a"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    permission = postgresql.ENUM("update", "delete", name="timer_permission", create_type=False)
    user_type = postgresql.ENUM("creator", "participant", name="timer_user_type", create_type=False)
    permission.create(op.get_bind(), checkfirst=False)
    user_type.create(op.get_bind(), checkfirst=False)

    op.create_table(
        "timers",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("start_time < end_time", name="ck_timers_time_range"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "timer_participants",
        sa.Column("timer_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "permissions",
            postgresql.ARRAY(permission),
            server_default=sa.text("'{}'::timer_permission[]"),
            nullable=False,
        ),
        sa.Column("user_type", user_type, nullable=False),
        sa.ForeignKeyConstraint(["timer_id"], ["timers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("timer_id", "user_id"),
    )
    op.create_index("ix_timer_participants_user_id", "timer_participants", ["user_id"])
    op.create_index(
        "uq_timer_participants_creator",
        "timer_participants",
        ["timer_id"],
        unique=True,
        postgresql_where=sa.text("user_type = 'creator'"),
    )
    op.create_table(
        "timer_checkpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timer_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["timer_id"], ["timers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_timer_checkpoints_timer_id_time", "timer_checkpoints", ["timer_id", "time"])


def downgrade() -> None:
    raise RuntimeError("Dropping timer storage would destroy data; use a reviewed backup or forward migration")
