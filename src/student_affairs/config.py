from src.config_root_schema import load_root_settings, require_not_none
from src.student_affairs.config_schema import StudentAffairsSettings

root_settings = load_root_settings()
settings: StudentAffairsSettings = require_not_none(
    root_settings.student_affairs_service,
    "Student affairs service settings are not configured, please check your settings file",
)