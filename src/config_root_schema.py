from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field, SecretStr

from src.clubs.config_schema import ClubsSettings
from src.config_primitives import BaseSchema
from src.maps.config_schema import MapsSettings
from src.student_affairs.config_schema import StudentAffairsSettings


class AccountsSettings(BaseSchema):
    """InNoHassle Accounts integration settings"""

    api_url: str = "https://api.innohassle.ru/accounts/v0"
    "URL of the Accounts API"
    api_jwt_token: SecretStr | None = None
    "JWT token for accessing the Accounts API as a service"


class Settings(BaseSchema):
    schema_: str | None = Field(None, alias="$schema")
    accounts: AccountsSettings = AccountsSettings()
    "Shared InNoHassle Accounts integration settings"

    maps_service: MapsSettings = MapsSettings()
    clubs_service: ClubsSettings | None = None
    student_affairs_service: StudentAffairsSettings | None = None

    @classmethod
    def from_yaml(cls, path: Path) -> Settings:
        with open(path, encoding="utf-8") as f:
            yaml_config = yaml.safe_load(f)

        return cls.model_validate(yaml_config)

    @classmethod
    def save_schema(cls, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            schema = {"$schema": "https://json-schema.org/draft-07/schema", **cls.model_json_schema()}
            yaml.dump(schema, f, sort_keys=False)


@lru_cache(maxsize=1)
def load_root_settings(path: Path | None = None) -> Settings:
    if path is None:
        path = Path(os.getenv("SETTINGS_PATH", "settings.yaml"))
    return Settings.from_yaml(path)



def require_not_none[T](value: T | None, message: str = "Expected non-None value") -> T:
    if value is None:
        raise ValueError(message)
    return value
