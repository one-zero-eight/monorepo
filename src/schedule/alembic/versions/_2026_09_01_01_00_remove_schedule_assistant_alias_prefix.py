"""remove schedule assistant alias prefix

Revision ID: 5ce5340dc3cb
Revises: 90c1de28f6a1
Create Date: 2026-09-01 01:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5ce5340dc3cb"
down_revision: str | None = "90c1de28f6a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_PREFIX = "schedule-assistant-"


def _rename_aliases(table_name: str, *, add_prefix: bool) -> None:
    table = sa.table(table_name, sa.column("group_alias", sa.String(length=255)))
    if add_prefix:
        op.execute(
            table.update()
            .where(table.c.group_alias.startswith("english-"))
            .values(group_alias=sa.literal(OLD_PREFIX) + table.c.group_alias)
        )
        return
    op.execute(
        table.update()
        .where(table.c.group_alias.startswith(OLD_PREFIX))
        .where(table.c.group_alias.startswith(f"{OLD_PREFIX}english-"))
        .values(group_alias=sa.func.substr(table.c.group_alias, len(OLD_PREFIX) + 1))
    )


def upgrade() -> None:
    _rename_aliases("users_x_favorite_groups", add_prefix=False)
    _rename_aliases("users_x_hidden_groups", add_prefix=False)


def downgrade() -> None:
    _rename_aliases("users_x_hidden_groups", add_prefix=True)
    _rename_aliases("users_x_favorite_groups", add_prefix=True)
