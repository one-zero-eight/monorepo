from pydantic import Field, SecretStr

from src.common_config import BaseSchema, MongoDatabaseSettings, ServiceSettingsBase


class MinioSettings(BaseSchema):
    endpoint: str = Field(default="127.0.0.1:9000", examples=["127.0.0.1:9000", "minio:9000"])
    "URL of the target service."
    secure: bool = False
    "Use https connection to the service."
    region: str | None = None
    "Region of the service."
    bucket: str = "clubs"
    "Name of the bucket in the service."
    access_key: str = "onezeroeight"
    "Access key (user ID) of a user account in the service."
    secret_key: SecretStr = SecretStr("herewethinkbig")
    "Secret key (password) for the user account."
    club_logos_prefix: str = "logos/"


class ClubsSettings(ServiceSettingsBase):
    """Settings for the application."""

    mongo: MongoDatabaseSettings = MongoDatabaseSettings()
    "Configuration for MongoDB"
    minio: MinioSettings = MinioSettings()
    "Configuration for S3 object storage"
    superadmin_emails: list[str] = []
    "Innomails of superadmins who can set admin roles"
