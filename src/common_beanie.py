__all__ = ["BeanieDocument", "BeanieStore", "setup_beanie"]

import os
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, cast

from beanie import Document, PydanticObjectId, UnionDoc, View, init_beanie
from pydantic import ConfigDict, Field, SecretStr
from pymongo import AsyncMongoClient, timeout
from pymongo.errors import ConnectionFailure

from src.logging_ import logger


class BeanieDocument(Document):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    if TYPE_CHECKING:
        id: PydanticObjectId
    else:
        id: PydanticObjectId = Field(
            default_factory=lambda: (
                None
            ),  # We use lambda because we dont want to have "None" default in openapi schema, yet we want to have None default in python
            description="MongoDB document ObjectID",
            serialization_alias="id",
        )

    class Settings:
        keep_nulls = False
        max_nesting_depth = 1


class BeanieStore:
    def __init__(
        self,
        client: AsyncMongoClient,
        document_models: Sequence[type[Document | UnionDoc | View] | str],
        database_name: str,
    ) -> None:
        self._client = client
        self._document_models = tuple(document_models)
        self.original_database_name = database_name
        self.current_database_name = database_name

    @property
    def client(self) -> AsyncMongoClient:
        return self._client

    async def rotate_database(self, database_name: str) -> None:
        """
        Switch to a different database. Used for testing.
        """
        if "PYTEST_CURRENT_TEST" not in os.environ:
            raise RuntimeError("Cannot rotate database outside of a test")
        self.current_database_name = database_name
        mongo_db = self._client.get_database(database_name)
        await init_beanie(
            database=mongo_db,
            document_models=self._document_models,
            recreate_views=True,
        )

    async def clear_database(self) -> None:
        """
        Remove data but keep collections and indexes. Used for testing.
        """
        if "PYTEST_CURRENT_TEST" not in os.environ:
            raise RuntimeError("Cannot clear database outside of a test")
        database_name = self.current_database_name
        mongo_db = self._client.get_database(database_name)

        cursor = await mongo_db.list_collections()
        async for collection_info in cursor:
            info = cast(Mapping[str, Any], collection_info)
            collection_name = cast(str, info["name"])
            collection_type = info.get("type")

            if collection_name.startswith("system."):
                continue

            if collection_type != "collection":
                continue

            await mongo_db.get_collection(collection_name).delete_many({})

    async def close(self) -> None:
        await self._client.close()


async def setup_beanie(
    database_uri: SecretStr | str,
    default_database_name: str,
    document_models: Sequence[type[Document | UnionDoc | View] | str],
) -> BeanieStore:
    """
    Setup MongoDB database and initialize Beanie. Returns :class:`BeanieStore`; call ``close()`` on teardown.
    Pass ``default_database_name`` as service name (e.g. ``"clubs"``). Runs a Mongo health check and logs it.
    """
    client = AsyncMongoClient(
        database_uri.get_secret_value() if isinstance(database_uri, SecretStr) else database_uri,
        connectTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )

    try:
        with timeout(1):
            server_info = await client.server_info()
            version = server_info["version"]
            logger.info(f"Connected to MongoDB v{version}")
    except ConnectionFailure as e:  # pragma: no cover
        logger.critical(f"Could not connect to MongoDB: {e}")

    mongo_db = client.get_default_database(default=default_database_name)
    # ^ default from URI path, or default_database_name if the URI has no database segment
    store = BeanieStore(client, document_models, mongo_db.name)
    await init_beanie(database=mongo_db, document_models=document_models, recreate_views=True)
    return store
