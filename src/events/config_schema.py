from pydantic import Field, SecretStr

from src.common_config import MinioSettings, MongoDatabaseSettings, ServiceSettingsBase
from src.common_pydantic import BaseSchema


class ClubsIntegrationSettings(BaseSchema):
    """InNoHassle Clubs integration settings."""

    api_url: str = "https://api.innohassle.ru/clubs/v0"
    "URL of the Clubs API"
    api_key: SecretStr
    "API key for accessing the Clubs API as a service"


class EventsSettings(ServiceSettingsBase):
    """Settings for the Events service."""

    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
    minio: MinioSettings = Field(default_factory=lambda: MinioSettings(bucket="events"))
    "Configuration for S3 object storage"
    images_prefix: str = "events-images/"
    "Prefix for event images in MinIO"
    innohassle_url: str = "https://innohassle.ru"
    "Base URL of the InNoHassle frontend (used for club host links and ICS event URLs)"
    ics_default_duration_hours: float = 2
    "Default event duration in hours for ICS feeds (DTEND = DTSTART + duration)"
    event_manager_emails: list[str] = Field(default_factory=list)
    "Innomails of users who can act as event managers (can use any external host)"
    moderator_emails: list[str] = Field(default_factory=list)
    "Innomails of users who can review and publish events"
    locales: list[str] = Field(default_factory=lambda: ["en", "ru"])
    "Allowed event locales"
    clubs: ClubsIntegrationSettings
    "Clubs service integration settings"
