__all__ = ["SqlEventGroupRepository"]

from collections.abc import Iterable
from typing import cast

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.schedule.modules.event_groups.schemas import (
    CreateEventGroup,
    CreateEventGroupWithoutTags,
    UpdateEventGroup,
    ViewEventGroup,
)
from src.schedule.modules.tags.repository import SqlTagRepository
from src.schedule.storages.sql.models import EventGroup, EventGroupTagAssociation


class SqlEventGroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @property
    def tags(self) -> SqlTagRepository:
        return SqlTagRepository(self.session)

    # ----------------- CRUD ----------------- #

    async def create(self, group: CreateEventGroup) -> ViewEventGroup:
        tags_ids = []
        if group.tags:
            tags_ids = [tag.id for tag in await self.tags.batch_create_or_read(group.tags)]

        session = self.session
        q = insert(EventGroup).values(group.model_dump(exclude={"tags"})).returning(EventGroup)
        obj = await session.scalar(q)
        if obj is None:
            raise RuntimeError("Failed to create event group")
        if tags_ids:
            q = (
                insert(EventGroupTagAssociation)
                .values([{"object_id": obj.id, "tag_id": tag_id} for tag_id in tags_ids])
                .on_conflict_do_nothing()
            )
            await session.execute(q)

        created = await self.read(obj.id)
        if created is None:
            raise RuntimeError("Failed to read created event group")
        return created

    async def batch_create(self, groups: list[CreateEventGroupWithoutTags]) -> list[ViewEventGroup]:
        if not groups:
            return []

        session = self.session
        q = insert(EventGroup).returning(EventGroup)
        created = await session.scalars(q, params=[group.model_dump() for group in groups])
        return [ViewEventGroup.model_validate(group) for group in created]

    async def create_or_update(self, group: CreateEventGroup) -> int:
        session = self.session
        insert_stmt = insert(EventGroup).values(group.model_dump(exclude={"tags"}))
        update_dict = {c.name: c for c in cast(Iterable, insert_stmt.excluded) if not c.primary_key}
        q = insert_stmt.on_conflict_do_update(index_elements=[EventGroup.alias], set_=update_dict).returning(
            EventGroup.id
        )
        obj_id = (await session.execute(q)).scalar_one()

        tags_ids = []
        if group.tags:
            tags_ids = [tag.id for tag in await self.tags.batch_create_or_read(group.tags)]

        await self.tags.set_tags_to_event_group(obj_id, tags_ids)
        return obj_id

    async def batch_create_or_read(self, groups: list[CreateEventGroup]) -> list[ViewEventGroup]:
        session = self.session
        insert_stmt = insert(EventGroup).values([group.model_dump(exclude={"tags"}) for group in groups])
        update_dict = {c.name: c for c in cast(Iterable, insert_stmt.excluded) if not c.primary_key}

        q = insert_stmt.on_conflict_do_update(index_elements=[EventGroup.alias], set_=update_dict).returning(
            EventGroup.id
        )
        obj_ids = (await session.scalars(q)).all()

        # set tags
        _create_tags = list({tag for group in groups for tag in group.tags})
        db_tags = await self.tags.batch_create_or_read(_create_tags)
        alias_x_tag = {(tag.alias, tag.type): tag for tag in db_tags}
        event_group_id_x_tags_ids = {}
        for group, group_id in zip(groups, obj_ids):
            tag_ids = [alias_x_tag[(tag.alias, tag.type)].id for tag in group.tags]
            event_group_id_x_tags_ids[group_id] = tag_ids
        await self.tags.batch_set_tags_to_event_group(event_group_id_x_tags_ids)

        session = self.session
        objs = await session.scalars(select(EventGroup).where(EventGroup.id.in_(obj_ids)))
        return [ViewEventGroup.model_validate(obj) for obj in objs]

    async def read(self, group_id: int) -> ViewEventGroup | None:
        session = self.session
        group = await session.scalar(
            select(EventGroup).where(EventGroup.id == group_id).execution_options(populate_existing=True)
        )
        return ViewEventGroup.model_validate(group) if group is not None else None

    async def get_only_path(self, group_id: int) -> str | None:
        session = self.session
        q = select(EventGroup.path).where(EventGroup.id == group_id).where(EventGroup.path.isnot(None))
        path: str | None = await session.scalar(q)
        return path

    async def read_all(self) -> list[ViewEventGroup]:
        session = self.session
        groups = await session.scalars(select(EventGroup))
        return [ViewEventGroup.model_validate(group) for group in groups]

    async def read_by_path(self, path: str) -> ViewEventGroup | None:
        session = self.session
        group = await session.scalar(select(EventGroup).where(EventGroup.path == path))
        return ViewEventGroup.model_validate(group) if group is not None else None

    async def read_by_alias(self, alias: str) -> ViewEventGroup | None:
        session = self.session
        group = await session.scalar(select(EventGroup).where(EventGroup.alias == alias))
        return ViewEventGroup.model_validate(group) if group is not None else None

    async def batch_read_ids_by_aliases(self, aliases: list[str]) -> dict[str, int | None]:
        session = self.session
        q = select(EventGroup.id, EventGroup.alias).where(EventGroup.alias.in_(aliases))
        rows = (await session.execute(q)).all()
        result = dict.fromkeys(aliases, None)
        for row in rows:
            result[row.alias] = row.id
        return result

    async def existing_aliases(self, aliases: list[str]) -> set[str]:
        if not aliases:
            return set()
        session = self.session
        q = select(EventGroup.alias).where(EventGroup.alias.in_(aliases))
        return set(await session.scalars(q))

    async def update(self, event_group_id: int, event_group: UpdateEventGroup) -> ViewEventGroup:
        session = self.session
        q = (
            update(EventGroup)
            .where(EventGroup.id == event_group_id)
            .values(**event_group.model_dump(exclude_unset=True))
            .returning(EventGroup.id)
        )
        updated_id = await session.scalar(q)
        if updated_id is None:
            raise RuntimeError(f"Event group {event_group_id} not found")
        updated = await self.read(updated_id)
        if updated is None:
            raise RuntimeError(f"Event group {event_group_id} not found after update")
        return updated

    async def batch_update(self, event_groups: dict[int, UpdateEventGroup]) -> list[ViewEventGroup]:
        if not event_groups:
            return []
        session = self.session
        await session.execute(
            update(EventGroup),
            params=[
                {"id": group_id, **group.model_dump(exclude_unset=True)} for group_id, group in event_groups.items()
            ],
        )
        groups = await session.scalars(select(EventGroup).where(EventGroup.id.in_(event_groups)))
        return [ViewEventGroup.model_validate(group) for group in groups]

    async def delete_by_alias(self, alias: str) -> None:
        session = self.session
        q = delete(EventGroup).where(EventGroup.alias == alias)
        await session.execute(q)

    async def delete_by_tag_alias(self, tag_alias: str) -> int:
        tag = await self.tags.read_by_alias(tag_alias)
        if tag is None:
            return 0

        session = self.session
        # select event groups with that tag
        q = (
            select(EventGroup.id)
            .join(EventGroup.tags_association)
            .where(EventGroup.tags_association.any(tag_id=tag.id))
        )
        event_group_ids = (await session.execute(q)).scalars().all()
        if not event_group_ids:
            return 0

        # delete event groups
        q = delete(EventGroup).where(EventGroup.id.in_(event_group_ids))
        await session.execute(q)
        return len(event_group_ids)

    # ^^^^^^^^^^^^^^^^^ CRUD ^^^^^^^^^^^^^^^^^ #

    async def update_timestamp(self, group_id: int):
        session = self.session
        # updated_at
        q = update(EventGroup).where(EventGroup.id == group_id).values()
        await session.execute(q)
