import os
from pathlib import Path

import yaml

from src.config_schema import Scene, Settings

settings_path = os.getenv("SETTINGS_PATH", "settings.yaml")
settings: Settings = Settings.from_yaml(Path(settings_path))


def load_scenes(path: Path = Path("scenes.yaml")) -> list[Scene]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        return [Scene.model_validate(scene) for scene in data.get("scenes", [])]


scenes: list[Scene] = load_scenes()
