__all__ = ["Ownership", "OwnershipEnum", "setup_ownership_method"]

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession


class OwnershipEnum(StrEnum):
    default = "default"
    moderator = "moderator"
    owner = "owner"
    delete = "delete"


async def setup_ownership_method(
    ownership_model, session: AsyncSession, object_id: int, user_id: int, role_alias: OwnershipEnum
) -> None:
    if role_alias is OwnershipEnum.delete:
        q = (
            delete(ownership_model)
            .where(ownership_model.user_id == user_id)
            .where(ownership_model.object_id == object_id)
        )
        await session.execute(q)
    else:
        q = insert(ownership_model).values(
            user_id=user_id,
            object_id=object_id,
            role_alias=role_alias,
        )
        q = q.on_conflict_do_update(
            index_elements=[ownership_model.user_id, ownership_model.object_id],
            set_={"role_alias": role_alias.value},
        )
        await session.execute(q)
    await session.commit()


class Ownership(BaseModel):
    user_id: int
    object_id: int

    role_alias: OwnershipEnum

    @field_validator("role_alias", mode="before")
    @classmethod
    def _validate_ownership_enum(cls, v):
        return OwnershipEnum(v)

    model_config = ConfigDict(from_attributes=True)
