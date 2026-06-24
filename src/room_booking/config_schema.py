from typing import Literal

from pydantic import Field, SecretStr

from src.common_config import BaseSchema, ServiceSettingsBase


class Room(BaseSchema):
    """Room description."""

    id: str
    "Room slug"
    title: str
    "Room title"
    short_name: str
    "Shorter version of room title"
    resource_email: str = Field(exclude=True)
    "Email of the room resource"
    capacity: int | None = None
    "Room capacity, amount of people"
    access_level: Literal["yellow", "red", "special"] | None = None
    "Access level to the room. Yellow = for students. Red = for employees. Special = special rules apply."
    restrict_daytime: bool = False
    "Prohibit to book during working hours. True = this room is available only at night 19:00-8:00, or full day on weekends."


class AccessToRoom(BaseSchema):
    email: str
    "Email of the user"
    reason: str = ""
    "Reason for access (f.e. 'Leader of 'one-zero-eight' club', or `Academic Tutorship`)"


class BmpExchange(BaseSchema):
    """Dedicated BMP mailbox; bookings go to the default calendar with Auto markers."""

    username: str
    "BMP account email"
    password: SecretStr
    "Password for the BMP account"


class Exchange(BaseSchema):
    """Exchange (Outlook) integration settings"""

    ews_endpoint: str = "https://mail.innopolis.ru/EWS/Exchange.asmx"
    "URL of the EWS endpoint"
    username: str
    "Username for accessing the EWS endpoint (email)"
    password: SecretStr
    "Password for accessing the EWS endpoint"
    ews_callback_url: str | None = None
    "URL of the EWS callback for push subscription"
    bmp: BmpExchange
    "Dedicated BMP account and Auto calendar"


class RoomBookingSettings(ServiceSettingsBase):
    api_key: SecretStr
    "Secret key for accessing API by external services"
    access_lists: dict[str, list[AccessToRoom]] = Field(default_factory=dict)
    "Dictionary of access lists (room id -> access list)"
    ttl_bookings_from_account_calendar: int = 60
    "TTL for the bookings from account calendar cache in seconds"
    ttl_bookings_from_busy_info: int = 60
    "TTL for the bookings from busy info cache in seconds"
    recently_canceled_booking_ttl_sec: int = 300
    "TTL for the recently-canceled booking IDs cache in seconds (skip cancel if already canceled within this window)"
    exchange: Exchange
    "Exchange (Outlook) integration settings"
    bmp_batch_confirm_timeout_s: int = 180
    "Seconds to wait for each room meeting response during BMP batch booking confirm"
