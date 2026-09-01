from pydantic import Field, SecretStr

from src.common_config import ServiceSettingsBase
from src.common_pydantic import BaseSchema


class RoomBookingSettings(BaseSchema):
    """Room Booking API integration settings."""

    api_url: str = "https://api.innohassle.ru/room-booking/v0/"
    "URL of the Room Booking API"
    api_key: SecretStr
    "Shared secret for accessing the room-booking API as a service"


class ScheduleAssistantSettings(ServiceSettingsBase):
    """Settings for the Schedule Assistant service."""

    app_root_path: str = "/schedule-assistant/v0"
    api_key: SecretStr
    "Shared secret for service-to-service Schedule Assistant API access"
    published_group_kinds: list[str] | None = Field(default_factory=lambda: ["english"])
    "Student group kinds published as virtual event groups; null publishes all kinds"
    moderator_emails: list[str] = Field(default_factory=list)
    "Innopolis emails allowed to access moderator-only endpoints"
    db_url: SecretStr = Field(
        examples=[
            "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/schedule_assistant",
            "postgresql+psycopg://postgres:postgres@postgres:5432/schedule_assistant",
        ],
    )
    "PostgreSQL database connection URL"
    booking: RoomBookingSettings
    "Room Booking API integration settings"
