from beanie import PydanticObjectId
from pydantic import Field

from src.clubs.mongo import Club, ClubSchema

CLUB_SCHEMA_FIELDS = set(ClubSchema.model_fields)


class CreateClub(ClubSchema):
    pass


class UpdateClub(ClubSchema):
    new_leader_email: str | None = Field(default=None, exclude=True)

    def to_club_schema(self) -> ClubSchema:
        clean_data = self.model_dump(
            include=CLUB_SCHEMA_FIELDS,
            exclude_unset=True,
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
    update_data = data.model_dump(include=CLUB_SCHEMA_FIELDS, exclude_unset=True)
    result = await Club.get_pymongo_collection().update_one(
        {"_id": id},
        {"$set": update_data, "$unset": {"new_leader_email": ""}},
    )
    return await Club.get(id) if result.matched_count else None


async def delete(id: PydanticObjectId) -> bool:
    result = await Club.find_one({"_id": id}).delete()
    return bool(result and (result.deleted_count > 0))


async def get_pending_updates() -> list[Club]:
    return await Club.find({"pending_update": {"$ne": None}}).to_list()


async def approve_update(id: PydanticObjectId) -> Club | None:
    club = await Club.get(id)
    if not club or not club.pending_update:
        return club
    
    update_data = club.pending_update.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(club, k, v)
    
    club.pending_update = None
    await club.save()
    return club


async def reject_update(id: PydanticObjectId) -> Club | None:
    club = await Club.get(id)
    if not club or not club.pending_update:
        return club
        
    club.pending_update = None
    await club.save()
    return club
