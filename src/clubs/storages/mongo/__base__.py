__all__ = ["CustomDocument"]

from typing import Annotated

from beanie import Document, PydanticObjectId
from pydantic import ConfigDict, Field, GetJsonSchemaHandler, WithJsonSchema
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

MongoDbIdSchema = {
    "type": "string",
    "format": "objectid",
    "example": "5eb7cf5a86d9755df3a6c593",
}
MongoDbId = Annotated[
    PydanticObjectId,
    WithJsonSchema(
        MongoDbIdSchema,
        mode="serialization",
    ),
]


class CustomDocument(Document):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    id: MongoDbId = Field(  # type: ignore[assignment]
        default=None, description="MongoDB document ObjectID", serialization_alias="id"
    )

    class Settings:
        keep_nulls = False
        max_nesting_depth = 1

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        __core_schema: CoreSchema,
        __handler: GetJsonSchemaHandler,
    ) -> JsonSchemaValue:
        schema = super().__get_pydantic_json_schema__(__core_schema, __handler)
        if __handler.mode == "serialization":
            if "required" in schema and "id" not in schema["required"]:
                schema["required"].append("id")
            if "required" not in schema:
                schema["required"] = ["id"]
        return schema
