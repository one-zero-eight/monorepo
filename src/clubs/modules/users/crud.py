from src.storages.mongo.user import User, UserRole


async def read_by_innohassle_id(innohassle_id: str) -> User | None:
    return await User.find_one(User.innohassle_id == innohassle_id)


async def change_role_of_user(innohassle_id: str, role: UserRole):
    obj = await read_by_innohassle_id(innohassle_id)
    if obj is None:
        # Create a user if it does not exist
        return await User(innohassle_id=innohassle_id, role=role).create()
    obj.role = role
    await obj.save()
    return obj
