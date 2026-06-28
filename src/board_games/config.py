from src.board_games.config_schema import BoardGamesSettings
from src.config_root_schema import load_root_settings, require_not_none

root_settings = load_root_settings()
settings: BoardGamesSettings = require_not_none(
    root_settings.board_games_service,
    "Board games service settings are not configured, please check your settings file",
)
