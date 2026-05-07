from src.clubs.config_schema import ClubsSettings
from src.config_root_schema import load_root_settings, require_not_none

root_settings = load_root_settings()
settings: ClubsSettings = require_not_none(
    root_settings.clubs_service,
    "Clubs service settings are not configured, please check your settings file",
)
