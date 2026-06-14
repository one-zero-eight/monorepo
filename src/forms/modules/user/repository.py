__all__ = ["user_repository"]

from beanie import PydanticObjectId

from src.forms.modules.user.schemas import CreateUser
from src.forms.mongo import User


# noinspection PyMethodMayBeStatic
class UserRepository:
    async def create(self, user: CreateUser) -> User:
        created = User(**user.model_dump())

        return await created.insert()

    async def read(self, user_id: PydanticObjectId) -> User | None:
        return await User.get(user_id)

    async def read_id_by_innohassle_id(self, innohassle_id: str) -> PydanticObjectId | None:
        user = await User.find_one(User.innohassle_id == innohassle_id)
        return user.id if user else None

    async def exists(self, user_id: PydanticObjectId) -> bool:
        return bool(await User.find(User.id == user_id, limit=1).count())

    async def is_banned(self, user_id: str | PydanticObjectId) -> bool:
        return False


user_repository: UserRepository = UserRepository()
