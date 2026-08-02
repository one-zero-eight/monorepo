from src.config_root_schema import load_root_settings, require_not_none
from src.schedule.config_schema import ScheduleSettings

root_settings = load_root_settings()
settings: ScheduleSettings = require_not_none(
    root_settings.schedule_service,
    "Schedule service settings are not configured, please check your settings file",
)
