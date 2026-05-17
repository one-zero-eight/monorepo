import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field, SecretStr, model_validator

from src.clubs.config_schema import ClubsSettings
from src.common_config import BaseSchema, Environment
from src.maps.config_schema import MapsSettings
from src.student_affairs.config_schema import StudentAffairsSettings


class AccountsSettings(BaseSchema):
    """InNoHassle Accounts integration settings"""

    api_url: str = "https://api.innohassle.ru/accounts/v0"
    "URL of the Accounts API"
    api_jwt_token: SecretStr
    "JWT token for accessing the Accounts API as a service"
    mock: bool = False
    """
    If true (development only), accept `Authorization: Bearer` values as JSON shaped like
    `UserTokenData` instead of validating a JWT. JWKS fetch is skipped.
    """


class Settings(BaseSchema):
    schema_: str | None = Field(default=None, alias="$schema", init=False)
    accounts: AccountsSettings
    "Shared InNoHassle Accounts integration settings"

    maps_service: MapsSettings = MapsSettings()
    clubs_service: ClubsSettings | None = None
    student_affairs_service: StudentAffairsSettings | None = None

    @model_validator(mode="after")
    def accounts_mock_requires_development(self) -> Settings:
        if not self.accounts.mock:
            return self
        contexts: list[tuple[str, Environment]] = [("maps_service", self.maps_service.environment)]
        if self.clubs_service is not None:
            contexts.append(("clubs_service", self.clubs_service.environment))
        if self.student_affairs_service is not None:
            contexts.append(("student_affairs_service", self.student_affairs_service.environment))
        bad = [(name, env.value) for name, env in contexts if env != Environment.DEVELOPMENT]
        if bad:
            names = ", ".join(f"{n}={e}" for n, e in bad)
            raise ValueError(
                f"accounts.mock is allowed only when all configured services use environment={Environment.DEVELOPMENT.value!r}; got {names}"
            )
        return self

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
def _load_root_settings_cached(path: Path) -> Settings:
    return Settings.from_yaml(path)


def load_root_settings(path: Path | None = None) -> Settings:
    if path is None:
        path = Path(os.getenv("SETTINGS_PATH", "settings.yaml"))
    return _load_root_settings_cached(path.expanduser().resolve())


def require_not_none[T](value: T | None, message: str = "Expected non-None value") -> T:
    if value is None:  # pragma: no cover
        raise ValueError(message)  # pragma: no cover
    return value  # pragma: no cover
