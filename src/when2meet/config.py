from src.config_root_schema import load_root_settings, require_not_none
from src.when2meet.config_schema import When2MeetSettings

root_settings = load_root_settings()
settings: When2MeetSettings = require_not_none(
    root_settings.when2meet_service,
    "When2Meet settings are not configured, please check your settings file",
)
