from src.config_root_schema import load_root_settings, require_not_none
from src.tabletennis.config_schema import TabletennisSettings

root_settings = load_root_settings()
settings: TabletennisSettings = require_not_none(
    root_settings.tabletennis_service,
    "Tabletennis service settings are not configured, please check your settings file",
)
