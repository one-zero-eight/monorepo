__all__ = ["CustomDocument", "setup_mongodb"]

from collections.abc import Sequence

from beanie import Document, PydanticObjectId, UnionDoc, View, init_beanie
from pydantic import ConfigDict, Field, SecretStr
from pymongo import AsyncMongoClient, timeout
from pymongo.errors import ConnectionFailure

from src.logging_ import logger


class CustomDocument(Document):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: PydanticObjectId = Field(  # type: ignore[assignment]
        default_factory=lambda: (
            None
        ),  # We use lambda because we dont want to have "None" default in openapi schema, yet we want to have None default in python
        description="MongoDB document ObjectID",
        serialization_alias="id",
    )

    class Settings:
        keep_nulls = False
        max_nesting_depth = 1


async def setup_mongodb(
    database_uri: SecretStr | str,
    default_database_name: str | None,
    document_models: Sequence[type[Document] | type[UnionDoc] | type[View] | str],
) -> AsyncMongoClient:
    """
    Setup MongoDB database and initialize Beanie, return the client which you should close on the teardown. Pass default_database_name as service name (f.e. "clubs"). Also it run healthcheck for the database and log it.
    """
    client: AsyncMongoClient = AsyncMongoClient(
        database_uri.get_secret_value() if isinstance(database_uri, SecretStr) else database_uri,
        connectTimeoutMS=5000,
        serverSelectionTimeoutMS=5000,
        tz_aware=True,
    )

    # healthcheck mongo
    try:
        with timeout(1):
            server_info = await client.server_info()
            version = server_info["version"]
            logger.info(f"Connected to MongoDB v{version}")
    except ConnectionFailure as e:  # pragma: no cover
        logger.critical(f"Could not connect to MongoDB: {e}")

    mongo_db = client.get_default_database(default=default_database_name)
    # ^ It will use the default database name from uri or default_database_name if database name is not specified in the uri
    await init_beanie(database=mongo_db, document_models=document_models, recreate_views=True)
    return client
