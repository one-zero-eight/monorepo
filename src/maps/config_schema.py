from pathlib import Path

from src.config_primitives import ServiceSettingsBase


class MapsSettings(ServiceSettingsBase):
    static_mount_path: str = "/static"
    "Path to mount static files"
    static_directory: Path = Path("src/maps/static")
    "Path to the directory with static files"
