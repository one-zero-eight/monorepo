from beanie import PydanticObjectId

from src.clubs.mongo import Club, ClubSchema


class CreateClub(ClubSchema):
    pass


class UpdateClub(ClubSchema):
    new_leader_email: str | None = None

    def to_club_schema(self) -> ClubSchema:
        clean_data = self.model_dump(
            include=set(ClubSchema.model_fields.keys()),
            exclude_unset=True
        )
        return ClubSchema.model_validate(clean_data)


async def create(data: CreateClub) -> Club:
    return await Club.model_validate(data, from_attributes=True).create()


async def read(id: PydanticObjectId) -> Club | None:
    return await Club.get(id)


async def read_by_slug(slug: str) -> Club | None:
    return await Club.find_one(Club.slug == slug)


async def read_by_leader_innohassle_id(leader_innohassle_id: str) -> list[Club]:
    return await Club.find(Club.leader_innohassle_id == leader_innohassle_id).to_list()


async def read_all() -> list[Club]:
    return await Club.all().to_list()


async def update(id: PydanticObjectId, data: ClubSchema) -> Club | None:
    obj = await Club.get(id)
    if obj:
        await obj.set(data.model_dump(exclude_unset=True))
    return obj


async def delete(id: PydanticObjectId) -> bool:
    result = await Club.find_one({"_id": id}).delete()
    return bool(result and (result.deleted_count > 0))
