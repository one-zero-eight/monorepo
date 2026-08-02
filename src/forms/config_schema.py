from pydantic import Field, SecretStr

from src.common_config import MongoDatabaseSettings, ServiceSettingsBase
from src.common_pydantic import BaseSchema


class LinksSettings(BaseSchema):
    """Links and signature settings"""

    signature_secret: SecretStr
    "Secret used to sign and verify form payload"


class FormsSettings(ServiceSettingsBase):
    """Settings for the application."""

    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
    links: LinksSettings
    "Links and signature settings"
