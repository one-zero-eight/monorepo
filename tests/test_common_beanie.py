from uuid import uuid4

import pytest
from beanie import Document, PydanticObjectId, init_beanie
from pymongo import AsyncMongoClient

from src.common_beanie import BeanieDocumentMixin
from src.common_pydantic import BaseSchema
from tests.conftest_runtime_settings import load_root_settings


@pytest.mark.asyncio
async def test_models_defined_after_initialization_keep_defaults_and_database_isolation():
    settings = load_root_settings().clubs_service
    assert settings is not None
    client = AsyncMongoClient(settings.mongo.uri.get_secret_value())
    database_prefix = f"test-beanie-{uuid4().hex}"
    first_database = client[f"{database_prefix}-first"]
    second_database = client[f"{database_prefix}-second"]

    class FirstDocument(BeanieDocumentMixin, Document):
        value: str
        optional_value: str | None = None

    try:
        await init_beanie(database=first_database, document_models=[FirstDocument])
        first = await FirstDocument(value="first").insert()
        assert isinstance(first.id, PydanticObjectId)

        # Services import their models lazily, after another service has started.
        class SecondDocument(BeanieDocumentMixin, Document):
            value: str
            optional_value: str | None = None

        class ThirdSchema(BaseSchema):
            value: str

        class ThirdDocument(ThirdSchema, BeanieDocumentMixin, Document):
            pass

        await init_beanie(database=second_database, document_models=[SecondDocument, ThirdDocument])
        for model in (SecondDocument, ThirdDocument):
            document = model(value="second")
            assert document.id is None
            assert document.revision_id is None
            await document.insert()
            assert isinstance(document.id, PydanticObjectId)
            assert await model.find_one(model.id == document.id) == document
            assert document.model_dump(by_alias=True)["id"] == document.id
            schema = model.model_json_schema(mode="serialization")
            assert "id" in schema["properties"]
            assert "_id" not in schema["properties"]
            assert "default" not in schema["properties"]["id"]

        # Reinitializing one service must not redirect an already running one.
        await init_beanie(database=second_database, document_models=[SecondDocument, ThirdDocument])
        await FirstDocument(value="another first").insert()
        assert await FirstDocument.count() == 2
        assert await SecondDocument.count() == 1
        assert await first_database["SecondDocument"].count_documents({}) == 0
        assert await second_database["FirstDocument"].count_documents({}) == 0

        stored_first = await first_database["FirstDocument"].find_one({"_id": first.id})
        assert stored_first is not None
        assert "optional_value" not in stored_first
        assert "revision_id" not in stored_first
        assert "_class_id" not in stored_first
    finally:
        await client.drop_database(first_database.name)
        await client.drop_database(second_database.name)
        await client.close()
