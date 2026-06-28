from pydantic import Field

from src.common_config import MongoDatabaseSettings, ServiceSettingsBase


class BoardGamesSettings(ServiceSettingsBase):
    """Settings for Board Games service."""

    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
    superadmin_emails: list[str] = Field(default_factory=list)
    "Innomails of superadmins who can set admin roles"
