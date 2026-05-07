from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr


class Environment(StrEnum):
    DEVELOPMENT = "development"
    PRODUCTION = "production"


class SettingBaseModel(BaseModel):
    model_config = ConfigDict(use_attribute_docstrings=True, extra="forbid")


class Accounts(SettingBaseModel):
    """InNoHassle Accounts integration settings"""

    api_url: str = "https://api.innohassle.ru/accounts/v0"
    "URL of the Accounts API"
    api_jwt_token: SecretStr
    "JWT token for accessing the Accounts API as a service"


class OmnideskSettings(SettingBaseModel):
    base_url: str
    "URL in format: https://mydomain.omnidesk.ru"
    jwt_marker: SecretStr
    "JWT secret marker for user auth in Omnidesk. See instructions: https://support.omnidesk.ru/knowledge_base/item/54180"

    @property
    def api_base_url(self) -> str:
        return f"{self.base_url}/api"

    @property
    def jwt_access_base_url(self) -> str:
        return f"{self.base_url}/access/jwt"

    @property
    def default_redirect_to(self) -> str:
        return f"{self.base_url}/user/cases/"


class Settings(SettingBaseModel):
    """Settings for the application."""

    schema_: str | None = Field(None, alias="$schema")
    environment: Environment = Environment.DEVELOPMENT
    "App environment flag"
    app_root_path: str = ""
    'Prefix for the API path (e.g. "/api/v0")'
    cors_allow_origin_regex: str = ".*"
    "Allowed origins for CORS: from which domains requests to the API are allowed. Specify as a regex: `https://.*.innohassle.ru`"
    accounts: Accounts
    "InNoHassle Accounts integration settings"
    omnidesk: OmnideskSettings
    "Omnidesk integration settings"

    @classmethod
    def from_yaml(cls, path: Path) -> "Settings":
        with open(path) as f:
            yaml_config = yaml.safe_load(f)

        return cls.model_validate(yaml_config)

    @classmethod
    def save_schema(cls, path: Path) -> None:
        with open(path, "w") as f:
            schema = {"$schema": "https://json-schema.org/draft-07/schema", **cls.model_json_schema()}
            yaml.dump(schema, f, sort_keys=False)
