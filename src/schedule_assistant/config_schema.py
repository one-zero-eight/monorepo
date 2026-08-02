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
    moderator_emails: list[str] = Field(default_factory=list)
    "Innopolis emails allowed to access moderator-only endpoints"
    preference_link_secret: SecretStr = SecretStr("dev-preference-link-secret-change-me")
    "HMAC secret for signed instructor preference share links"
    db_url: SecretStr = Field(
        examples=[
            "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/schedule_assistant",
            "postgresql+psycopg://postgres:postgres@postgres:5432/schedule_assistant",
        ],
    )
    "PostgreSQL database connection URL"
    booking: RoomBookingSettings
    "Room Booking API integration settings"
