from src.config_root_schema import load_root_settings, require_not_none
from src.room_booking.config_schema import RoomBookingSettings

root_settings = load_root_settings()
settings: RoomBookingSettings = require_not_none(
    root_settings.room_booking_service,
    "Room booking settings are not configured, please check your settings file",
)
