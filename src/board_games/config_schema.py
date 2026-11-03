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
    max_photo_size_bytes: int = Field(default=10 * 1024 * 1024, ge=1)
    "Maximum uploaded board game photo size in bytes"
    max_photo_pixels: int = Field(default=20_000_000, ge=1)
    "Maximum decoded board game photo size in pixels"
    superadmin_emails: list[str] = Field(default_factory=list)
    "Innomails of superadmins who can set admin roles"
