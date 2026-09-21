import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from pymongo import MongoClient
from pymongo.errors import OperationFailure

from src.migrations import migrate_mongo
from tests.conftest_runtime_settings import SUITE_MONGO_AUTH, SUITE_MONGO_NETLOC, SUITE_MONGO_USER


def test_unique_index_failure_preserves_duplicate_data_and_existing_index():
    database_name = f"migration-index-{uuid4().hex}"
    uri = (
        f"mongodb://{SUITE_MONGO_USER}:{SUITE_MONGO_AUTH}@{SUITE_MONGO_NETLOC}/{database_name}"
        "?authSource=admin&replicaSet=rs0&directConnection=true"
    )
    with MongoClient(uri) as client:
        database = client[database_name]
        try:
            documents = [{"_id": "first", "key": "same", "extra": 1}, {"_id": "second", "key": "same", "extra": 2}]
            database.records.insert_many(documents)
            database.records.create_index("extra", name="preserve_existing_index")
            with pytest.raises(OperationFailure):
                asyncio.run(
                    migrate_mongo(
                        "tabletennis",
                        uri,
                        database_name,
                        migration_path=Path(__file__).parent / "fixtures/unique_index",
                    )
                )
            assert list(database.records.find().sort("_id")) == documents
            assert database.migrations_log.count_documents({}) == 0
            assert "preserve_existing_index" in database.records.index_information()
            assert "unique_key" not in database.records.index_information()
        finally:
            client.drop_database(database_name)
