from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Environment(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class SettingBaseModel(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")


class LegendEntry(SettingBaseModel):
    legend_id: str
    "ID of the legend"
    color: str | None = None
    "Color of the legend"
    legend: str | None = None
    "Description of the legend (may contain multiple lines)"

    @model_validator(mode="after")
    def set_legend_as_legend_id(self):
        if self.legend is None:
            self.legend = self.legend_id
        return self


class Area(SettingBaseModel):
    svg_polygon_id: str | None = None
    "ID of the polygon in the SVG"
    title: str | None = None
    "Title of the area"
    ru_title: str | None = None
    "Title in Russian"
    legend_id: str | None = None
    "ID of the legend (if any)"
    description: str | None = None
    "Description of the area"
    people: list[str] = []
    "List of people for this area"
    prioritized: bool = False
    "Priority for multi-floor areas"
    room_booking_id: str | None = None
    "ID of the room in Room Booking API (if any)"
    scene_pointer: str | None = None
    "Maps scene name with which the area is associated"


class Scene(SettingBaseModel):
    scene_id: str
    "ID of the scene"
    title: str
    "Title of the scene"
    svg_file: str
    "Path to the SVG file in /static"
    legend: list[LegendEntry] = []
    "Legend of the scene"
    areas: list[Area] = []
    "Areas of the scene"


class Accounts(SettingBaseModel):
    """InNoHassle Accounts integration settings"""

    api_url: str = "https://api.innohassle.ru/accounts/v0"
    "URL of the Accounts API"


class Settings(SettingBaseModel):
    """Settings for the application."""

    schema_: str = Field(None, alias="$schema")
    environment: Environment = Environment.DEVELOPMENT
    "App environment flag"
    app_root_path: str = ""
    'Prefix for the API path (e.g. "/api/v0")'
    cors_allow_origin_regex: str = ".*"
    """
    Allowed origins for CORS: from which domains requests to the API are allowed.
    Specify as a regex: `https://.*.innohassle.ru`
    """
    static_mount_path: str = "/static"
    "Path to mount static files"
    static_directory: Path = Path("static")
    "Path to the directory with static files"
    accounts: Accounts = Accounts()
    "InNoHassle-Accounts integration settings"

    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        with open(path, encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        return cls.model_validate(yaml_config)

    @classmethod
    def save_schema(cls, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            schema = {"$schema": "https://json-schema.org/draft-07/schema", **cls.model_json_schema()}
            yaml.dump(schema, f, sort_keys=False)
