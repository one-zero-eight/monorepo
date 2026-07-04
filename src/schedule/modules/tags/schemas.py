__all__ = ["CreateTag", "UpdateTag", "ViewTag"]

import json

from pydantic import BaseModel, ConfigDict, Json, field_validator


class CreateTag(BaseModel, frozen=True):
    alias: str
    type: str | None = None
    name: str | None = None
    satellite: Json | None = None

    @field_validator("satellite", mode="before")
    def _validate_satellite(cls, v):
        if isinstance(v, dict):
            v = json.dumps(v)
        return v


class ViewTag(BaseModel):
    id: int
    alias: str
    type: str | None = None
    name: str | None = None
    satellite: dict | None = None

    # ownerships: list[Ownership] = Field(default_factory=list)
    @field_validator("satellite", mode="before")
    def _validate_satellite(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    model_config = ConfigDict(from_attributes=True)


class UpdateTag(BaseModel):
    alias: str | None = None
    type: str | None = None
    name: str | None = None
    satellite: Json | None = None

    @field_validator("satellite", mode="before")
    def _validate_satellite(cls, v):
        if isinstance(v, dict):
            v = json.dumps(v)
        return v
