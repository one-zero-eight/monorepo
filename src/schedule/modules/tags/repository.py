__all__ = ["SqlTagRepository"]

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.schedule.models import EventGroupTagAssociation, Tag
from src.schedule.modules.tags.schemas import CreateTag, UpdateTag, ViewTag


class SqlTagRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------ CRUD ------------------ #
    async def create_or_read(self, tag: CreateTag) -> ViewTag:
        session = self.session
        q = insert(Tag).values(**tag.model_dump()).on_conflict_do_nothing().returning(Tag)
        created = await session.scalar(q)
        if created is not None:
            return ViewTag.model_validate(created)
        found = await session.scalar(select(Tag).where(Tag.alias == tag.alias, Tag.type == tag.type))
        if found is None:
            raise RuntimeError(f"Tag not found after conflict: {tag.alias}")
        return ViewTag.model_validate(found)

    async def batch_create_or_read(self, tags: list[CreateTag]) -> list[ViewTag]:
        if not tags:
            return []
        session = self.session
        q = (
            insert(Tag)
            .on_conflict_do_update(
                index_elements=[Tag.alias, Tag.type],
                set_={"id": Tag.id},
            )
            .values([tag.model_dump() for tag in tags])
            .returning(Tag)
        )

        db_tags = await session.scalars(q)
        return [ViewTag.model_validate(tag) for tag in db_tags]

    async def read(self, id: int) -> ViewTag | None:
        session = self.session
        tag = await session.scalar(select(Tag).where(Tag.id == id))
        return ViewTag.model_validate(tag) if tag is not None else None

    async def read_all(self) -> list[ViewTag]:
        session = self.session
        tags = await session.scalars(select(Tag))
        return [ViewTag.model_validate(tag) for tag in tags]

    async def batch_read(self, tag_ids: list[int]) -> list[ViewTag]:
        if not tag_ids:
            return []
        session = self.session
        tags = await session.scalars(select(Tag).where(Tag.id.in_(tag_ids)))
        return [ViewTag.model_validate(tag) for tag in tags]

    async def read_by_name(self, name: str) -> ViewTag | None:
        session = self.session
        tag = await session.scalar(select(Tag).where(Tag.name == name))
        return ViewTag.model_validate(tag) if tag is not None else None

    async def update(self, id: int, tag: UpdateTag) -> ViewTag:
        session = self.session
        values = tag.model_dump(exclude_unset=True)
        if values:
            q = update(Tag).where(Tag.id == id).values(**values).returning(Tag)
        else:
            q = select(Tag).where(Tag.id == id)
        updated = await session.scalar(q)
        return ViewTag.model_validate(updated)

    async def delete(self, id: int) -> None:
        session = self.session
        await session.execute(delete(Tag).where(Tag.id == id))

    # ^^^^^^^^^^^^^^^^^^^^ CRUD ^^^^^^^^^^^^^^^^^^^^ #

    async def read_by_alias(self, alias: str) -> ViewTag | None:
        session = self.session
        tag = await session.scalar(select(Tag).where(Tag.alias == alias))
        return ViewTag.model_validate(tag) if tag is not None else None

    async def set_tags_to_event_group(self, event_group_id: int, tag_ids: list[int]) -> None:
        session = self.session
        table = EventGroupTagAssociation
        q = delete(table).where(table.object_id == event_group_id)
        await session.execute(q)

        q = (
            insert(table)
            .values([{"object_id": event_group_id, "tag_id": tag_id} for tag_id in tag_ids])
            .on_conflict_do_nothing()
        )
        await session.execute(q)

    async def batch_set_tags_to_event_group(self, tags_mapping: dict[int, list[int]]) -> None:
        if not tags_mapping:
            return

        session = self.session
        table = EventGroupTagAssociation
        # clear all tags
        to_clear = tuple(tags_mapping.keys())
        if to_clear:
            q = delete(table).where(table.object_id.in_(to_clear))
            await session.execute(q)

        values = [
            {
                "object_id": event_group_id,
                "tag_id": tag_id,
            }
            for event_group_id, tag_ids in tags_mapping.items()
            for tag_id in tag_ids
            if tag_ids
        ]
        if values:
            q = insert(table).values(values).on_conflict_do_nothing()
            await session.execute(q)

    async def delete_by_alias(self, alias: str) -> None:
        session = self.session
        q = delete(Tag).where(Tag.alias == alias)
        await session.execute(q)

    async def delete_by_type(self, type_: str) -> None:
        session = self.session
        q = delete(Tag).where(Tag.type == type_)
        await session.execute(q)
