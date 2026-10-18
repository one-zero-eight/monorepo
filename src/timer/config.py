from src.config_root_schema import load_root_settings, require_not_none
from src.timer.config_schema import TimerSettings

root_settings = load_root_settings()
settings: TimerSettings = require_not_none(
    root_settings.timer_service,
    "Timer settings are not configured, please check your settings file",
)
