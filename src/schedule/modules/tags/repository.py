__all__ = ["SqlTagRepository", "tag_repository"]

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.schedule.modules.crud import AbstractCRUDRepository, CRUDFactory
from src.schedule.modules.ownership import OwnershipEnum, setup_ownership_method
from src.schedule.modules.tags.schemas import CreateTag, UpdateTag, ViewTag
from src.schedule.storages.sql import SQLAlchemyStorage
from src.schedule.storages.sql.models import EventGroup, Tag

CRUD: AbstractCRUDRepository[
    CreateTag,
    ViewTag,
    UpdateTag,
] = CRUDFactory(Tag, CreateTag, ViewTag, UpdateTag)


class SqlTagRepository:
    storage: SQLAlchemyStorage

    def update_storage(self, storage: SQLAlchemyStorage):
        self.storage = storage

    def _create_session(self) -> AsyncSession:
        return self.storage.create_session()

    # ------------------ CRUD ------------------ #
    async def create_or_read(self, tag: CreateTag) -> ViewTag:
        async with self._create_session() as session:
            created = await CRUD.create_if_not_exists(session, tag)
            if created is None:
                created = await CRUD.read_by(session, only_first=True, alias=tag.alias, type=tag.type)
            return created

    async def batch_create_or_read(self, tags: list[CreateTag]) -> list[ViewTag]:
        if not tags:
            return []
        async with self._create_session() as session:
            q = (
                insert(Tag)
                .on_conflict_do_update(
                    index_elements=[Tag.alias, Tag.type],
                    set_={"id": Tag.id},
                )
                .values([tag.model_dump() for tag in tags])
                .options(
                    selectinload(Tag.ownerships),
                )
                .returning(Tag)
            )

            tags = await session.scalars(q)
            await session.commit()
            return [ViewTag.model_validate(tag) for tag in tags]

    async def read(self, id: int) -> ViewTag:
        async with self._create_session() as session:
            return await CRUD.read(session, id=id)

    async def read_all(self) -> list[ViewTag]:
        async with self._create_session() as session:
            return await CRUD.read_all(session)

    async def batch_read(self, tag_ids: list[int]) -> list[ViewTag]:
        async with self._create_session() as session:
            return await CRUD.batch_read(session, pkeys=[{"id": tag_id} for tag_id in tag_ids])

    async def read_by_name(self, name: str) -> ViewTag:
        async with self._create_session() as session:
            return await CRUD.read_by(session, only_first=True, name=name)

    async def update(self, id: int, tag: UpdateTag) -> ViewTag:
        async with self._create_session() as session:
            return await CRUD.update(session, data=tag, id=id)

    async def delete(self, id: int) -> None:
        async with self._create_session() as session:
            await CRUD.delete(session, id=id)

    # ^^^^^^^^^^^^^^^^^^^^ CRUD ^^^^^^^^^^^^^^^^^^^^ #

    async def read_by_alias(self, alias: str) -> ViewTag | None:
        async with self._create_session() as session:
            return await CRUD.read_by(session, only_first=True, alias=alias)

    async def setup_ownership(self, tag_id: int, user_id: int, role_alias: OwnershipEnum) -> None:
        async with self._create_session() as session:
            OwnershipClass = Tag.Ownership
            return await setup_ownership_method(OwnershipClass, session, tag_id, user_id, role_alias)

    async def set_tags_to_event_group(self, event_group_id: int, tag_ids: list[int]) -> None:
        async with self._create_session() as session:
            table = Tag.__tags_associations__[EventGroup.__tablename__]
            q = delete(table).where(table.object_id == event_group_id)
            await session.execute(q)

            q = (
                insert(table)
                .values([{"object_id": event_group_id, "tag_id": tag_id} for tag_id in tag_ids])
                .on_conflict_do_nothing()
            )
            await session.execute(q)
            await session.commit()

    async def batch_set_tags_to_event_group(self, tags_mapping: dict[int, list[int]]) -> None:
        if not tags_mapping:
            return

        async with self._create_session() as session:
            table = Tag.__tags_associations__[EventGroup.__tablename__]
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

            await session.commit()

    async def delete_by_alias(self, alias: str) -> None:
        async with self._create_session() as session:
            q = delete(Tag).where(Tag.alias == alias)
            await session.execute(q)
            await session.commit()

    async def delete_by_type(self, type_: str) -> None:
        async with self._create_session() as session:
            q = delete(Tag).where(Tag.type == type_)
            await session.execute(q)
            await session.commit()


tag_repository: SqlTagRepository = SqlTagRepository()
