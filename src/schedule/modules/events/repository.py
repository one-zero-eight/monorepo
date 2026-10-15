__all__ = ["SqlEventRepository"]

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from src.schedule.models import Event, EventPatch
from src.schedule.modules.events.schemas import (
    AddEventPatch,
    CreateEvent,
    UpdateEvent,
    UpdateEventPatch,
    ViewEvent,
    ViewEventPatch,
)


class SqlEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ----------------- CRUD ----------------- #

    async def create(self, event: CreateEvent) -> ViewEvent:
        session = self.session
        db_event = Event(
            **event.model_dump(exclude={"patches"}),
            patches=[EventPatch(**patch.model_dump()) for patch in event.patches],
        )
        session.add(db_event)
        await session.flush()
        await session.refresh(db_event)
        return ViewEvent.model_validate(db_event)

    async def read(self, event_id: int) -> ViewEvent | None:
        session = self.session
        q = select(Event).where(Event.id == event_id).options(selectinload(Event.patches))
        event = await session.scalar(q)
        return ViewEvent.model_validate(event) if event is not None else None

    async def update(self, event_id: int, event: UpdateEvent) -> ViewEvent:
        session = self.session
        q = (
            update(Event)
            .where(Event.id == event_id)
            .values(**event.model_dump(exclude_unset=True))
            .returning(Event)
            .options(selectinload(Event.patches))
        )
        updated = await session.scalar(q)
        return ViewEvent.model_validate(updated)

    async def delete(self, event_id: int) -> None:
        session = self.session
        await session.execute(delete(Event).where(Event.id == event_id))

    # ^^^^^^^^^^^^^^^^^^ CRUD ^^^^^^^^^^^^^^^ #
    # ----------------- PATCHES ----------------- #
    async def add_patch(self, event_id: int, patch: AddEventPatch) -> ViewEventPatch:
        session = self.session
        q = (
            postgres_insert(EventPatch)
            .values(parent_id=event_id, **patch.model_dump())
            .returning(EventPatch)
            .options(joinedload(EventPatch.parent))
        )
        event_patch = await session.scalar(q)
        return ViewEventPatch.model_validate(event_patch)

    async def read_patches(self, event_id: int) -> list[ViewEventPatch]:
        session = self.session
        q = select(EventPatch).where(EventPatch.parent_id == event_id).options(joinedload(EventPatch.parent))
        event_patches = await session.scalars(q)
        return [ViewEventPatch.model_validate(event_patch) for event_patch in event_patches]

    async def update_patch(self, patch_id: int, patch: UpdateEventPatch) -> ViewEventPatch:
        session = self.session
        q = (
            update(EventPatch)
            .where(EventPatch.id == patch_id)
            .values(**patch.model_dump(exclude_unset=True))
            .returning(EventPatch)
        )
        event_patch = await session.scalar(q)
        return ViewEventPatch.model_validate(event_patch)

    # ^^^^^^^^^^^^^^^^^^ PATCHES ^^^^^^^^^^^^^^^ #
