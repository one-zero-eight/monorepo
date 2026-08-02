from src.config_root_schema import load_root_settings, require_not_none
from src.guard.config_schema import GuardSettings

root_settings = load_root_settings()
settings: GuardSettings = require_not_none(
    root_settings.guard_service,
    "Guard service settings are not configured, please check your settings file",
)
