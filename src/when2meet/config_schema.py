from pydantic import Field

from src.common_config import MongoDatabaseSettings, ServiceSettingsBase
from src.common_pydantic import BaseSchema


class RoomBookingIntegrationSettings(BaseSchema):
    """InNoHassle Room Booking integration settings."""

    api_url: str = "https://api.innohassle.ru/room-booking/v0"
    "URL of the Room Booking API"


class When2MeetSettings(ServiceSettingsBase):
    service_name: str = "when2meet"
    "Human-readable service name returned by the health endpoint"
    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    "Configuration for MongoDB"
    room_booking: RoomBookingIntegrationSettings | None = None
    "Room Booking API integration settings"
