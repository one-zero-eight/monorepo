from pydantic import Field

from src.common_config import MinioSettings, MongoDatabaseSettings, ServiceSettingsBase


class BoardGamesSettings(ServiceSettingsBase):
    """Settings for Board Games service."""

    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
    minio: MinioSettings = Field(default_factory=MinioSettings)
    "Configuration for S3 object storage"
    superadmin_emails: list[str] = Field(default_factory=list)
    "Innomails of superadmins who can set admin roles"
