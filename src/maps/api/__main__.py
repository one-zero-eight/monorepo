import os
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
os.chdir(BASE_DIR)

SETTINGS_TEMPLATE = BASE_DIR / "settings.example.yaml"
SETTINGS_FILE = BASE_DIR / "settings.yaml"
PRE_COMMIT_CONFIG = BASE_DIR / ".pre-commit-config.yaml"
ACCOUNTS_TOKEN_URL = "https://api.innohassle.ru/accounts/v0/tokens/generate-service-token?sub=sports-local-dev&scopes=sport&only_for_me=true"


def ensure_settings_file():
    """
    Ensure `settings.yaml` exists. If not, copy `settings.example.yaml`.
    """
    if not SETTINGS_TEMPLATE.exists():
        print("❌ No `settings.example.yaml` found. Skipping copying.")
        return

    if SETTINGS_FILE.exists():
        print("✅ `settings.yaml` exists.")
        return

    shutil.copy(SETTINGS_TEMPLATE, SETTINGS_FILE)
    print(f"✅ Copied `{SETTINGS_TEMPLATE}` to `{SETTINGS_FILE}`")


def ensure_pre_commit_hooks():
    """
    Ensure `pre-commit` hooks are installed.
    """

    def is_pre_commit_installed():
        pre_commit_hook = BASE_DIR / ".git" / "hooks" / "pre-commit"
        return pre_commit_hook.exists() and os.access(pre_commit_hook, os.X_OK)

    if not PRE_COMMIT_CONFIG.exists():
        print("❌ No `.pre-commit-config.yaml` found. Skipping pre-commit setup.")
        return

    if is_pre_commit_installed():
        print("✅ Pre-commit hooks are installed.")
        return

    try:
        subprocess.run(
            ["uv", "run", "prek", "install", "--overwrite", "--prepare-hooks", "-t", "pre-commit", "-t", "commit-msg"],
            check=True,
            text=True,
        )
        print("✅ Pre-commit hooks installed successfully.")
    except subprocess.CalledProcessError as e:
        print(
            f"❌ Error setting up pre-commit hooks:\n{e.stderr}\nPlease, setup it manually with `uv run prek install --overwrite --prepare-hooks -t pre-commit -t commit-msg`"
        )


ensure_settings_file()
ensure_pre_commit_hooks()

import uvicorn  # noqa: E402

# Get arguments from command
args = sys.argv[1:]
extended_args = [
    "src.api.app:app",
    "--use-colors",
    "--proxy-headers",
    "--forwarded-allow-ips=*",
    *args,
]

print(f"🚀 Starting Uvicorn server: 'uvicorn {' '.join(extended_args)}'")
uvicorn.main.main(extended_args)
