"""A stock, idempotent migration used to exercise real transaction failures."""

from beanie import Document, free_fall_migration
from pymongo.asynchronous.client_session import AsyncClientSession


class HistoricalRecord(Document):
    class Settings:
        name = "records"


class Forward:
    @free_fall_migration(document_models=[HistoricalRecord])
    async def mark_records(self, session: AsyncClientSession) -> None:
        if not session.in_transaction:
            raise RuntimeError("A transaction is required")
        collection = HistoricalRecord.get_pymongo_collection()
        await collection.update_many(
            {"migrated": {"$exists": False}},
            {"$set": {"migrated": True}, "$inc": {"migration_count": 1}},
            session=session,
        )
        if await collection.find_one({"fail_migration": True}, session=session):
            raise RuntimeError("Deliberate failure after writing records")
