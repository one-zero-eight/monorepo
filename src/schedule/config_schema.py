from pathlib import Path

from pydantic import Field, SecretStr

from src.common_config import ServiceSettingsBase
from src.common_pydantic import BaseSchema


class MusicRoomSettings(BaseSchema):
    """InNoHassle Music Room integration settings."""

    api_url: str
    "URL of the Music Room API"
    api_key: SecretStr
    "API key for the Music Room API"


class SportSettings(BaseSchema):
    """Innopolis Sport integration settings."""

    api_url: str = "https://sport.innopolis.university/api"
    "URL of the Sport API"


class WorkshopsSettings(BaseSchema):
    """InNoHassle Workshops integration settings."""

    api_url: str = "https://api.innohassle.ru/workshops/v0"
    "URL of the Workshops API"
    api_key: SecretStr
    "API key for the Workshops API"


class RoomBookingIntegrationSettings(BaseSchema):
    """InNoHassle Room Booking integration settings."""

    api_url: str = "https://api.innohassle.ru/room-booking/v0"
    "URL of the Room Booking API"
    api_key: SecretStr
    "API key for the Room Booking API"


class ScheduleSettings(ServiceSettingsBase):
    """Settings for the Schedule service."""

    app_root_path: str = "/schedule/v0"
    db_url: SecretStr = Field(
        examples=[
            "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/postgres",
            "postgresql+asyncpg://postgres:postgres@postgres:5432/postgres",
        ],
    )
    "PostgreSQL database connection URL"
    predefined_dir: Path = Path("src/schedule/predefined")
    "Path to the directory with predefined ICS data"
    music_room: MusicRoomSettings | None = None
    "InNoHassle Music Room integration settings"
    sport: SportSettings = Field(default_factory=SportSettings)
    "Innopolis Sport integration settings"
    workshops: WorkshopsSettings | None = None
    "InNoHassle Workshops integration settings"
    room_booking: RoomBookingIntegrationSettings | None = None
    "InNoHassle Room Booking integration settings"
