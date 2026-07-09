from src.config_root_schema import load_root_settings, require_not_none
from src.schedule_assistant.config_schema import ScheduleAssistantSettings

root_settings = load_root_settings()
settings: ScheduleAssistantSettings = require_not_none(
    root_settings.schedule_assistant_service,
    "Schedule Assistant service settings are not configured, please check your settings file",
)
