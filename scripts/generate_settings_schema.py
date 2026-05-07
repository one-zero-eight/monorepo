import sys
from pathlib import Path

# add parent dir to sys.path
sys.path.append(str(Path(__file__).parents[1]))
from src.config_root_schema import Settings  # noqa: E402

Settings.save_schema(Path(__file__).parents[1] / "settings.schema.yaml")
