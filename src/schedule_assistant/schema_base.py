from pydantic import BaseModel, ConfigDict


class ScheduleAssistantSchema(BaseModel):
    model_config = ConfigDict(
        use_attribute_docstrings=True,
        extra="ignore",
        json_schema_serialization_defaults_required=True,
    )
