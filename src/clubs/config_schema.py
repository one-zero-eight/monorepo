from pydantic import Field, SecretStr

from src.config_primitives import BaseSchema, ServiceSettingsBase


class MinioSettings(BaseSchema):
    endpoint: str = "127.0.0.1:9000"
    "URL of the target service."
    secure: bool = False
    "Use https connection to the service."
    region: str | None = None
    "Region of the service."
    bucket: str = "search"
    "Name of the bucket in the service."
    access_key: str = Field(..., examples=["minioadmin"])
    "Access key (user ID) of a user account in the service."
    secret_key: SecretStr = Field(..., examples=["password"])
    "Secret key (password) for the user account."

    club_logos_prefix: str = "logos/"


class ClubsSettings(ServiceSettingsBase):
    """Settings for the application."""

    database_uri: SecretStr = Field(
        examples=[
            "mongodb://mongoadmin:secret@127.0.0.1:27017/db?authSource=admin",
            "mongodb://mongoadmin:secret@db:27017/db?authSource=admin",
        ]
    )
    "MongoDB database settings"
    minio: MinioSettings
    "Configuration for S3 object storage"
    superadmin_emails: list[str]
    "Innomails of superadmins who can set admin roles"
