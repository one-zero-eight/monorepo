import secrets
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parents[1]
SETTINGS_TEMPLATE = BASE_DIR / "settings.example.yaml"
SETTINGS_FILE = BASE_DIR / "settings.yaml"
PRE_COMMIT_CONFIG = BASE_DIR / ".pre-commit-config.yaml"
ACCOUNTS_TOKEN_URL = (
    "https://api.innohassle.ru/accounts/v0/tokens/"  # noqa: S105
    "generate-service-token?sub=monorepo-local-dev&scopes=users&scopes=sport&only_for_me=true"
)
PLACEHOLDER = "change-me"


def is_placeholder(value: object) -> bool:
    if value in ("", "...", PLACEHOLDER):
        return True
    return isinstance(value, str) and value.startswith(PLACEHOLDER)


def needs_user_secret(value: object) -> bool:
    return value is None or is_placeholder(value)


def get_settings() -> dict[str, Any]:
    """
    Load and return the settings from `settings.yaml` if it exists.
    """
    if not SETTINGS_FILE.exists():
        raise RuntimeError("❌ No `settings.yaml` found.")

    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        raise RuntimeError("❌ No `settings.yaml` found.") from e


def replace_settings_text(replacements: list[tuple[str, str]]) -> bool:
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        text = f.read()

    updated = False
    for old, new in replacements:
        if old not in text:
            continue
        text = text.replace(old, new, 1)
        updated = True

    if updated:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            f.write(text)

    return updated


def iter_placeholder_paths(value: object, prefix: str = "") -> Iterator[str]:
    if isinstance(value, dict):
        for key, nested in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            yield from iter_placeholder_paths(nested, path)
        return

    if isinstance(value, list):
        for index, nested in enumerate(value):
            yield from iter_placeholder_paths(nested, f"{prefix}[{index}]")
        return

    if is_placeholder(value):
        yield prefix


def ensure_settings_file() -> None:
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


def fill_auto_generated_secrets() -> None:
    settings = get_settings()
    replacements: list[tuple[str, str]] = []

    forms_service = settings.get("forms_service") or {}
    links = forms_service.get("links") or {}
    if is_placeholder(links.get("signature_secret")):
        secret = secrets.token_urlsafe(32)
        replacements.append(("signature_secret: change-me", f"signature_secret: {secret}"))

    room_booking_service = settings.get("room_booking_service") or {}
    if is_placeholder(room_booking_service.get("api_key")):
        api_key = secrets.token_urlsafe(24)
        replacements.append(("api_key: change-me", f"api_key: {api_key}"))

    if not replacements:
        return

    if replace_settings_text(replacements):
        print("✅ Generated local secrets in `settings.yaml`:")
        for _, new in replacements:
            key = new.split(":", 1)[0].strip()
            print(f"  - {key}")


def check_and_prompt_api_jwt_token() -> None:
    """
    Check if `accounts.api_jwt_token` is set in `settings.yaml`.
    Prompt the user to set it if it is missing, allow them to input it,
    and open the required URL in the default web browser.
    """
    import webbrowser

    settings = get_settings()
    accounts = settings.get("accounts", {})
    api_jwt_token = accounts.get("api_jwt_token")

    if not needs_user_secret(api_jwt_token):
        print("✅ `accounts.api_jwt_token` is specified.")
        return

    print("⚠️ `accounts.api_jwt_token` is missing in `settings.yaml`.")
    print(f"  ➡️ Opening the following URL to generate a token:\n  {ACCOUNTS_TOKEN_URL}")

    webbrowser.open(ACCOUNTS_TOKEN_URL)

    token = input("  🔑 Please paste the generated token below (or press Enter to skip):\n  > ").strip()

    if not token:
        print("  ⚠️ Token was not provided. Please manually update `settings.yaml` later.")
        print(f"  ➡️ Refer to the URL: {ACCOUNTS_TOKEN_URL}")
        return

    replacements = [
        ("api_jwt_token: change-me", f"api_jwt_token: {token}"),
        ("api_jwt_token: null", f"api_jwt_token: {token}"),
        ("api_jwt_token: ...", f"api_jwt_token: {token}"),
    ]
    try:
        if replace_settings_text(replacements):
            print("  ✅ `accounts.api_jwt_token` has been updated in `settings.yaml`.")
        else:
            print("  ⚠️ Could not find `api_jwt_token` placeholder in `settings.yaml`.")
    except OSError as e:
        print(f"  ❌ Error updating `settings.yaml`: {e}")


def warn_remaining_placeholders() -> None:
    settings = get_settings()
    paths = list(iter_placeholder_paths(settings))
    if not paths:
        return

    print("⚠️ Replace remaining `change-me` placeholders before using these settings:")
    for path in paths:
        print(f"  - {path}")


def prepare() -> None:
    ensure_settings_file()
    fill_auto_generated_secrets()
    check_and_prompt_api_jwt_token()
    warn_remaining_placeholders()


if __name__ == "__main__":
    prepare()
