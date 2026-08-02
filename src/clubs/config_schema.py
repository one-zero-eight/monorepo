import datetime as dtm

from pydantic import Field, SecretStr

from src.common_config import MinioSettings, MongoDatabaseSettings, ServiceSettingsBase


class ClubsSettings(ServiceSettingsBase):
    """Settings for the application."""

    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
    minio: MinioSettings = Field(default_factory=MinioSettings)
    "Configuration for S3 object storage"
    superadmin_emails: list[str] = Field(default_factory=list)
    "Innomails of superadmins who can set admin roles"
    api_key: SecretStr | None = None
    "API key for service-to-service integration (e.g. the Events service)"
    at: dtm.datetime = Field(default_factory=dtm.datetime.now)
