from pydantic import Field

from src.common_config import MongoDatabaseSettings, ServiceSettingsBase


class When2MeetSettings(ServiceSettingsBase):
    service_name: str = "when2meet"
    "Human-readable service name returned by the health endpoint"
    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
