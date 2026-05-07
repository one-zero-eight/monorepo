from src.config_root_schema import load_root_settings, require_not_none
from src.maps.config_schema import MapsSettings

root_settings = load_root_settings()
settings: MapsSettings = require_not_none(
    root_settings.maps_service,
    "Maps service settings are not configured, please check your settings file",
)
