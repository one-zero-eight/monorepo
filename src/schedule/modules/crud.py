__all__ = ["AbstractCRUDRepository", "crud_factory"]

from abc import ABCMeta, abstractmethod
from typing import Any, Literal, overload

from pydantic import BaseModel as PydanticModel
from sqlalchemy import ColumnElement, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption

from src.schedule.storages.sql.models.base import Base


class AbstractCRUDRepository[CreateType: PydanticModel, ViewType: PydanticModel, UpdateType: PydanticModel](
    metaclass=ABCMeta
):
    @abstractmethod
    async def create(self, session: AsyncSession, data: CreateType) -> ViewType:
        pass

    @abstractmethod
    async def create_if_not_exists(self, session: AsyncSession, data: CreateType) -> ViewType | None:
        pass

    @abstractmethod
    async def batch_create(self, session: AsyncSession, data: list[CreateType]) -> list[ViewType]:
        pass

    @abstractmethod
    async def read(self, session: AsyncSession, **pkeys) -> ViewType | None:
        pass

    @abstractmethod
    async def batch_read(self, session: AsyncSession, pkeys: list[dict[str, Any]]) -> list[ViewType]:
        pass

    @abstractmethod
    async def read_all(self, session: AsyncSession) -> list[ViewType]:
        pass

    @overload
    async def read_by(self, session: AsyncSession, only_first: Literal[True], **columns: Any) -> ViewType | None: ...

    @overload
    async def read_by(self, session: AsyncSession, only_first: Literal[False], **columns: Any) -> list[ViewType]: ...

    @overload
    async def read_by(
        self, session: AsyncSession, only_first: bool, **columns: Any
    ) -> list[ViewType] | ViewType | None: ...

    @abstractmethod
    async def read_by(
        self, session: AsyncSession, only_first: bool, **columns: Any
    ) -> list[ViewType] | ViewType | None:
        pass

    @abstractmethod
    async def update(self, session: AsyncSession, data: UpdateType, **pkeys) -> ViewType:
        pass

    @abstractmethod
    async def batch_update(
        self, session: AsyncSession, data: list[UpdateType], pkeys: list[dict[str, Any]]
    ) -> list[ViewType]:
        pass

    @abstractmethod
    async def delete(self, session: AsyncSession, **pkeys) -> None:
        pass


class _CRUDImpl[ModelT: Base, CreateT: PydanticModel, ViewT: PydanticModel, UpdateT: PydanticModel](
    AbstractCRUDRepository[CreateT, ViewT, UpdateT]
):
    def __init__(
        self,
        model: type[ModelT],
        create_schema: type[CreateT],
        view_schema: type[ViewT],
        update_schema: type[UpdateT],
        get_options: tuple[ExecutableOption, ...] = (),
    ) -> None:
        from sqlalchemy.inspection import inspect

        self._model = model
        self._view_schema = view_schema
        self._get_options = get_options
        mapper = inspect(model)
        self._primary_keys = [column.name for column in mapper.primary_key]
        _ = (create_schema, update_schema)

    def _pkey_clause(self, pkeys: dict[str, int]) -> ColumnElement[bool]:
        return and_(*[getattr(self._model, pk) == pkeys[pk] for pk in self._primary_keys])

    async def create(self, session: AsyncSession, data: CreateT) -> ViewT:
        from sqlalchemy import insert

        _insert_query = insert(self._model).returning(self._model)
        if self._get_options:
            _insert_query = _insert_query.options(*self._get_options)
        obj = await session.scalar(_insert_query, params=data.model_dump())
        await session.commit()
        return self._view_schema.model_validate(obj)

    async def create_if_not_exists(self, session: AsyncSession, data: CreateT) -> ViewT | None:
        from sqlalchemy.dialects.postgresql import insert as postgres_insert

        q = postgres_insert(self._model).values(**data.model_dump()).on_conflict_do_nothing().returning(self._model)
        if self._get_options:
            q = q.options(*self._get_options)
        obj = await session.scalar(q)
        await session.commit()
        if obj:
            return self._view_schema.model_validate(obj)
        return None

    async def batch_create(self, session: AsyncSession, data: list[CreateT]) -> list[ViewT]:
        from sqlalchemy import insert

        if not data:
            return []
        _insert_query = insert(self._model).returning(self._model)
        if self._get_options:
            _insert_query = _insert_query.options(*self._get_options)
        objs = await session.scalars(_insert_query, params=[obj.model_dump() for obj in data])
        await session.commit()
        return [self._view_schema.model_validate(obj) for obj in objs]

    async def read(self, session: AsyncSession, **pkeys) -> ViewT | None:
        from sqlalchemy import select

        q = select(self._model).where(self._pkey_clause(pkeys))
        if self._get_options:
            q = q.options(*self._get_options)
        obj = await session.scalar(q)
        if obj:
            return self._view_schema.model_validate(obj)
        return None

    async def batch_read(self, session: AsyncSession, pkeys: list[dict[str, Any]]) -> list[ViewT]:
        from sqlalchemy import select

        if not pkeys:
            return []

        q = select(self._model).where(
            or_(
                *[self._pkey_clause(pkey) for pkey in pkeys],
            )
        )

        if self._get_options:
            q = q.options(*self._get_options)
        objs = await session.scalars(q)

        return [self._view_schema.model_validate(obj) for obj in objs]

    async def read_all(self, session: AsyncSession) -> list[ViewT]:
        from sqlalchemy import select

        q = select(self._model)
        if self._get_options:
            q = q.options(*self._get_options)
        objs = await session.scalars(q)
        return [self._view_schema.model_validate(obj) for obj in objs]

    @overload
    async def read_by(self, session: AsyncSession, only_first: Literal[True], **columns: Any) -> ViewT | None: ...

    @overload
    async def read_by(self, session: AsyncSession, only_first: Literal[False], **columns: Any) -> list[ViewT]: ...

    @overload
    async def read_by(self, session: AsyncSession, only_first: bool, **columns: Any) -> list[ViewT] | ViewT | None: ...

    async def read_by(self, session: AsyncSession, only_first: bool, **columns: Any) -> list[ViewT] | ViewT | None:
        from sqlalchemy import select

        q = select(self._model).where(*[getattr(self._model, column) == value for column, value in columns.items()])
        if self._get_options:
            q = q.options(*self._get_options)
        if only_first:
            obj = await session.scalar(q)
            return self._view_schema.model_validate(obj) if obj else None
        objs = await session.scalars(q)
        return [self._view_schema.model_validate(obj) for obj in objs]

    async def update(self, session: AsyncSession, data: UpdateT, **pkeys) -> ViewT:
        from sqlalchemy import update as sql_update

        q = sql_update(self._model).values(**pkeys, **data.model_dump(exclude_unset=True)).returning(self._model)
        if self._get_options:
            q = q.options(*self._get_options)
        obj = await session.scalar(q)
        await session.commit()
        return self._view_schema.model_validate(obj)

    async def batch_update(
        self, session: AsyncSession, data: list[UpdateT], pkeys: list[dict[str, Any]]
    ) -> list[ViewT]:
        from sqlalchemy import update as sql_update

        if not data:
            return []

        await session.execute(
            sql_update(self._model),
            params=[{**pkey, **obj.model_dump(exclude_unset=True)} for pkey, obj in zip(pkeys, data)],
        )
        await session.commit()

        return await self.batch_read(session, pkeys)

    async def delete(self, session: AsyncSession, **pkeys) -> None:
        from sqlalchemy import delete

        q = delete(self._model).where(self._pkey_clause(pkeys))
        await session.execute(q)
        await session.commit()


def crud_factory[
    ModelT: Base,
    CreateT: PydanticModel,
    ViewT: PydanticModel,
    UpdateT: PydanticModel,
](
    model: type[ModelT],
    create_schema: type[CreateT],
    view_schema: type[ViewT],
    update_schema: type[UpdateT],
    get_options: tuple[ExecutableOption, ...] = (),
) -> AbstractCRUDRepository[CreateT, ViewT, UpdateT]:
    return _CRUDImpl(model, create_schema, view_schema, update_schema, get_options)
