__all__ = ["SqlEventRepository"]

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.schedule.modules.crud import crud_factory
from src.schedule.modules.events.schemas import (
    AddEventPatch,
    CreateEvent,
    UpdateEvent,
    UpdateEventPatch,
    ViewEvent,
    ViewEventPatch,
)
from src.schedule.storages.sql import SQLAlchemyStorage
from src.schedule.storages.sql.models import Event, EventPatch

CRUD = crud_factory(
    Event,
    CreateEvent,
    ViewEvent,
    UpdateEvent,
    get_options=(selectinload(Event.patches),),
)


class SqlEventRepository:
    storage: SQLAlchemyStorage

    def __init__(self, storage: SQLAlchemyStorage):
        self.storage = storage

    def _create_session(self) -> AsyncSession:
        return self.storage.create_session()

    # ----------------- CRUD ----------------- #

    async def create(self, event: CreateEvent) -> ViewEvent:
        async with self._create_session() as session:
            db_event = Event(
                **event.model_dump(exclude={"patches"}),
                patches=[EventPatch(**patch.model_dump()) for patch in event.patches],
            )
            session.add(db_event)
            await session.commit()
            # update event
            await session.refresh(db_event)
            return ViewEvent.model_validate(db_event)

    async def read(self, event_id: int) -> ViewEvent | None:
        async with self._create_session() as session:
            return await CRUD.read(session, id=event_id)

    async def update(self, event_id: int, event: UpdateEvent) -> ViewEvent:
        async with self._create_session() as session:
            return await CRUD.update(session, event, id=event_id)

    async def delete(self, event_id: int) -> None:
        async with self._create_session() as session:
            await CRUD.delete(session, id=event_id)

    # ^^^^^^^^^^^^^^^^^^ CRUD ^^^^^^^^^^^^^^^ #
    # ----------------- PATCHES ----------------- #
    async def add_patch(self, event_id: int, patch: AddEventPatch) -> ViewEventPatch:
        async with self._create_session() as session:
            q = (
                postgres_insert(EventPatch)
                .values(parent_id=event_id, **patch.model_dump())
                .returning(EventPatch)
                .options(joinedload(EventPatch.parent))
            )
            event_patch = await session.scalar(q)
            await session.commit()
            return ViewEventPatch.model_validate(event_patch)

    async def read_patches(self, event_id: int) -> list[ViewEventPatch]:
        async with self._create_session() as session:
            q = select(EventPatch).where(EventPatch.parent_id == event_id).options(joinedload(EventPatch.parent))
            event_patches = await session.scalars(q)
            return [ViewEventPatch.model_validate(event_patch) for event_patch in event_patches]

    async def update_patch(self, patch_id: int, patch: UpdateEventPatch) -> ViewEventPatch:
        async with self._create_session() as session:
            q = (
                update(EventPatch)
                .where(EventPatch.id == patch_id)
                .values(**patch.model_dump(exclude_unset=True))
                .returning(EventPatch)
            )
            event_patch = await session.scalar(q)
            await session.commit()
            return ViewEventPatch.model_validate(event_patch)

    # ^^^^^^^^^^^^^^^^^^ PATCHES ^^^^^^^^^^^^^^^ #
