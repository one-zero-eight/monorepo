from src.config_root_schema import load_root_settings, require_not_none
from src.events.config_schema import EventsSettings

root_settings = load_root_settings()
settings: EventsSettings = require_not_none(
    root_settings.events_service,
    "Events service settings are not configured, please check your settings file",
)
