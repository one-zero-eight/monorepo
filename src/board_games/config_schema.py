from pydantic import Field

from src.common_config import MinioSettings, MongoDatabaseSettings, ServiceSettingsBase


class BoardGamesMinioSettings(MinioSettings):
    bucket: str = "board-game-photos"
    board_game_photos_prefix: str = ""


class BoardGamesSettings(ServiceSettingsBase):
    """Settings for Board Games service."""

    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
    minio: BoardGamesMinioSettings = Field(default_factory=BoardGamesMinioSettings)
    "Configuration for S3 object storage"
    superadmin_emails: list[str] = Field(default_factory=list)
    "Innomails of superadmins who can set admin roles"
