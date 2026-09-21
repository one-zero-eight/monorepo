from typing import ClassVar

from beanie import Document, free_fall_migration
from pymongo import IndexModel


class Records(Document):
    key: str

    class Settings:
        name = "records"
        indexes: ClassVar = [IndexModel("key", unique=True, name="unique_key")]


class Forward:
    @free_fall_migration(document_models=[Records])
    async def mark_records(self, session):
        await Records.get_pymongo_collection().update_many({}, {"$set": {"migrated": True}}, session=session)
