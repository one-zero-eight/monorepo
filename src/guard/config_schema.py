from pathlib import Path

from pydantic import Field

from src.common_config import MongoDatabaseSettings, ServiceSettingsBase
from src.common_pydantic import BaseSchema


class GoogleServiceSettings(BaseSchema):
    """Google API settings (Service Account + Drive)"""

    service_account_file_path: Path = Path("service_account.json")
    """
    Path to the Google service account file with credentials.

    Plain ``Path`` (not ``FilePath``): the monorepo loads the whole root ``Settings`` for
    every service, so requiring the file to exist here would break other services that do
    not mount it. Existence is enforced lazily where the file is actually read.
    """
    subject: str | None = None
    "Email address to impersonate for domain-wide delegation (e.g., service@innoguard.ru)"
    drive_folder_id: str | None = None
    "Google Drive folder ID where new files will be created (optional)"


class GuardSettings(ServiceSettingsBase):
    """Settings for the application."""

    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
    innohassle_url: str = "https://innohassle.ru"
    "URL of the InNoHassle to use for links"
    base_url: str = "https://innohassle.ru"
    "Base URL for generating join links"
    google: GoogleServiceSettings = Field(default_factory=GoogleServiceSettings)
    "Google API settings (Service Account + Drive)"
