import os
import shutil
import subprocess
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
SETTINGS_TEMPLATE = BASE_DIR / "settings.example.yaml"
SETTINGS_FILE = BASE_DIR / "settings.yaml"
PRE_COMMIT_CONFIG = BASE_DIR / ".pre-commit-config.yaml"


def get_settings():
    """
    Load and return the settings from `settings.yaml` if it exists.
    """
    if not SETTINGS_FILE.exists():
        raise RuntimeError("❌ No `settings.yaml` found.")

    try:
        with open(SETTINGS_FILE) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError("❌ No `settings.yaml` found.") from e


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


def check_and_prompt_api_jwt_token():
    """
    Check if `accounts.api_jwt_token` is set in `settings.yaml`.
    Prompt the user to set it if it is missing, allow them to input it,
    and open the required URL in the default web browser.
    """
    import webbrowser

    ACCOUNTS_TOKEN_URL = (
        "https://api.innohassle.ru/accounts/v0/tokens/"
        "generate-service-token?sub=student-affairs-local-dev&scopes=users&only_for_me=true"
    )
    settings = get_settings()
    accounts = settings.get("accounts", {})
    api_jwt_token = accounts.get("api_jwt_token")

    if not api_jwt_token or api_jwt_token == "...":
        print("⚠️ `accounts.api_jwt_token` is missing in `settings.yaml`.")
        print(f"  ➡️ Opening the following URL to generate a token:\n  {ACCOUNTS_TOKEN_URL}")

        webbrowser.open(ACCOUNTS_TOKEN_URL)

        token = input("  🔑 Please paste the generated token below (or press Enter to skip):\n  > ").strip()

        if token:
            try:
                with open(SETTINGS_FILE) as f:
                    as_text = f.read()
                as_text = as_text.replace("api_jwt_token: null", f"api_jwt_token: {token}")
                as_text = as_text.replace("api_jwt_token: ...", f"api_jwt_token: {token}")
                with open(SETTINGS_FILE, "w") as f:
                    f.write(as_text)
                print("  ✅ `accounts.api_jwt_token` has been updated in `settings.yaml`.")
            except Exception as e:
                print(f"  ❌ Error updating `settings.yaml`: {e}")
        else:
            print("  ⚠️ Token was not provided. Please manually update `settings.yaml` later.")
            print(f"  ➡️ Refer to the URL: {ACCOUNTS_TOKEN_URL}")
    else:
        print("✅ `accounts.api_jwt_token` is specified.")


def prepare():
    ensure_settings_file()
    ensure_pre_commit_hooks()
    check_and_prompt_api_jwt_token()
