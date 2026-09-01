"""store event group preferences by alias

Revision ID: 90c1de28f6a1
Revises: ae37e0d0ee10
Create Date: 2026-09-01 00:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "90c1de28f6a1"
down_revision: str | None = "ae37e0d0ee10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _scalar(statement: sa.Executable, table_name: str) -> int:
    value = op.get_bind().scalar(statement)
    if value is None:
        raise RuntimeError(f"Migration verification query returned no value for {table_name}")
    return int(value)


def _row_count(table_name: str, table: sa.Table) -> int:
    return _scalar(sa.select(sa.func.count()).select_from(table), table_name)


def _verify_upgrade_source(table_name: str, table: sa.Table, event_groups: sa.TableClause) -> int:
    source_count = _row_count(table_name, table)
    unmapped_count = _scalar(
        sa.select(sa.func.count())
        .select_from(table.outerjoin(event_groups, event_groups.c.id == table.c.group_id))
        .where(sa.or_(event_groups.c.id.is_(None), event_groups.c.alias.is_(None))),
        table_name,
    )
    if unmapped_count:
        raise RuntimeError(f"Cannot migrate {table_name}: {unmapped_count} rows have no event group alias")

    collisions = (
        sa.select(table.c.user_id, event_groups.c.alias)
        .select_from(table.join(event_groups, event_groups.c.id == table.c.group_id))
        .group_by(table.c.user_id, event_groups.c.alias)
        .having(sa.func.count() > 1)
        .subquery()
    )
    collision_count = _scalar(sa.select(sa.func.count()).select_from(collisions), table_name)
    if collision_count:
        raise RuntimeError(f"Cannot migrate {table_name}: alias mapping would merge {collision_count} preference keys")
    return source_count


def _verify_upgraded_data(
    table_name: str,
    table: sa.Table,
    event_groups: sa.TableClause,
    source_count: int,
) -> None:
    migrated_count = _row_count(table_name, table)
    invalid_count = _scalar(
        sa.select(sa.func.count())
        .select_from(table.join(event_groups, event_groups.c.id == table.c.group_id))
        .where(table.c.group_alias.is_distinct_from(event_groups.c.alias)),
        table_name,
    )
    if migrated_count != source_count or invalid_count:
        raise RuntimeError(
            f"Failed to verify {table_name} upgrade: expected {source_count} rows, "
            f"found {migrated_count} with {invalid_count} invalid aliases"
        )


def _migrate_table(table_name: str, table: sa.Table) -> None:
    connection = op.get_bind()
    event_groups = sa.table("event_groups", sa.column("id"), sa.column("alias"))
    source_count = _verify_upgrade_source(table_name, table, event_groups)
    op.add_column(table_name, sa.Column("group_alias", sa.String(length=255), nullable=True))
    connection.execute(
        table.update().values(
            group_alias=sa.select(event_groups.c.alias).where(event_groups.c.id == table.c.group_id).scalar_subquery()
        )
    )
    _verify_upgraded_data(table_name, table, event_groups, source_count)
    op.alter_column(table_name, "group_alias", nullable=False)
    op.drop_constraint(f"{table_name}_group_id_fkey", table_name, type_="foreignkey")
    op.drop_constraint(f"{table_name}_pkey", table_name, type_="primary")
    op.drop_column(table_name, "group_id")
    op.create_primary_key(f"{table_name}_pkey", table_name, ["user_id", "group_alias"])
    if _row_count(table_name, table) != source_count:
        raise RuntimeError(f"Failed to verify {table_name} upgrade after replacing its primary key")


def upgrade() -> None:
    metadata = sa.MetaData()
    _migrate_table(
        "users_x_favorite_groups",
        sa.Table(
            "users_x_favorite_groups",
            metadata,
            sa.Column("user_id", sa.Integer()),
            sa.Column("group_id", sa.Integer()),
            sa.Column("group_alias", sa.String(length=255)),
        ),
    )
    _migrate_table(
        "users_x_hidden_groups",
        sa.Table(
            "users_x_hidden_groups",
            metadata,
            sa.Column("user_id", sa.Integer()),
            sa.Column("group_id", sa.Integer()),
            sa.Column("group_alias", sa.String(length=255)),
        ),
    )


def _downgrade_table(table_name: str, table: sa.Table) -> None:
    connection = op.get_bind()
    event_groups = sa.table("event_groups", sa.column("id"), sa.column("alias"))
    source_count = _row_count(table_name, table)
    unmapped_count = _scalar(
        sa.select(sa.func.count())
        .select_from(table.outerjoin(event_groups, event_groups.c.alias == table.c.group_alias))
        .where(event_groups.c.id.is_(None)),
        table_name,
    )
    if unmapped_count:
        raise RuntimeError(f"Cannot downgrade {table_name}: {unmapped_count} aliases do not map to local event groups")

    op.add_column(table_name, sa.Column("group_id", sa.Integer(), nullable=True))
    connection.execute(
        table.update().values(
            group_id=sa.select(event_groups.c.id).where(event_groups.c.alias == table.c.group_alias).scalar_subquery()
        )
    )
    invalid_count = _scalar(
        sa.select(sa.func.count())
        .select_from(table.join(event_groups, event_groups.c.alias == table.c.group_alias))
        .where(table.c.group_id.is_distinct_from(event_groups.c.id)),
        table_name,
    )
    if invalid_count or _row_count(table_name, table) != source_count:
        raise RuntimeError(f"Failed to verify {table_name} downgrade mapping")

    op.alter_column(table_name, "group_id", nullable=False)
    op.drop_constraint(f"{table_name}_pkey", table_name, type_="primary")
    op.drop_column(table_name, "group_alias")
    op.create_primary_key(f"{table_name}_pkey", table_name, ["user_id", "group_id"])
    op.create_foreign_key(
        f"{table_name}_group_id_fkey",
        table_name,
        "event_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    if _row_count(table_name, table) != source_count:
        raise RuntimeError(f"Failed to verify {table_name} downgrade after restoring its foreign key")


def downgrade() -> None:
    metadata = sa.MetaData()
    _downgrade_table(
        "users_x_hidden_groups",
        sa.Table(
            "users_x_hidden_groups",
            metadata,
            sa.Column("user_id", sa.Integer()),
            sa.Column("group_alias", sa.String(length=255)),
            sa.Column("group_id", sa.Integer()),
        ),
    )
    _downgrade_table(
        "users_x_favorite_groups",
        sa.Table(
            "users_x_favorite_groups",
            metadata,
            sa.Column("user_id", sa.Integer()),
            sa.Column("group_alias", sa.String(length=255)),
            sa.Column("group_id", sa.Integer()),
        ),
    )
