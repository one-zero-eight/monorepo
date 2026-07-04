from pydantic import Field

from src.common_config import MongoDatabaseSettings, ServiceSettingsBase


class TabletennisSettings(ServiceSettingsBase):
    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)

    admin_emails: list[str] = Field(default_factory=list, description="List of coach emails who can manage games")
