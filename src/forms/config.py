from src.config_root_schema import load_root_settings, require_not_none
from src.forms.config_schema import FormsSettings

root_settings = load_root_settings()
settings: FormsSettings = require_not_none(
    root_settings.forms_service,
    "Forms service settings are not configured, please check your settings file",
)
