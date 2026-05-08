"""Pytest pulls this module before importing test files; configure process env before any `src.*` imports."""

from __future__ import annotations

import datetime
import json
import os
import re
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qs, unquote, urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
os.environ["SETTINGS_PATH"] = str(_REPO_ROOT / "settings.test.yaml")

import httpx
import pytest
import respx
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwt
from joserfc.jwk import RSAKey
from pymongo import MongoClient
from testcontainers.core.container import DockerContainer

import src.config_root_schema as config_root_schema
from src.inh_accounts_sdk import inh_accounts


class MakeUserToken(Protocol):
    def __call__(
        self,
        uid: str,
        email: str,
        telegram_id: int | None = None,
        expires_in_seconds: int = 3600,
    ) -> str: ...


def _sync_loaded_service_settings(loaded: config_root_schema.Settings) -> None:
    service_config_modules = {
        "src.clubs.config": loaded.clubs_service,
        "src.maps.config": loaded.maps_service,
        "src.student_affairs.config": loaded.student_affairs_service,
    }
    for module_name, service_settings in service_config_modules.items():
        module = sys.modules.get(module_name)
        if module is not None:
            setattr(module, "settings", service_settings)


@pytest.fixture
def auth_header_factory(make_user_token: MakeUserToken):
    def _make(uid: str, email: str, expires_in_seconds: int = 3600) -> dict[str, str]:
        token = make_user_token(uid=uid, email=email, expires_in_seconds=expires_in_seconds)
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture
def superadmin_headers(auth_header_factory):
    return auth_header_factory("superadmin-1", "admin@innopolis.university")


@pytest.fixture
def user_headers(auth_header_factory):
    return auth_header_factory("test-user-1", "test-user-1@innopolis.university")


@pytest.fixture(autouse=True, scope="session")
def mongo_connection_url() -> Iterator[str]:
    mongo = (
        DockerContainer("mongo:8.0")
        .with_env("MONGO_INITDB_ROOT_USERNAME", "test")
        .with_env("MONGO_INITDB_ROOT_PASSWORD", "test")
        .with_exposed_ports(27017)
    )
    mongo.start()
    try:
        host = mongo.get_container_host_ip()
        port = mongo.get_exposed_port(27017)
        connection_url = f"mongodb://test:test@{host}:{port}/clubs?authSource=admin"

        deadline = time.monotonic() + 30
        while True:
            try:
                client = MongoClient(connection_url, serverSelectionTimeoutMS=1000)
                client.admin.command("ping")
                client.close()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.5)

        yield connection_url
    finally:
        mongo.stop()


@pytest.fixture(autouse=True)
def clean_clubs_db(mongo_connection_url: str) -> Iterator[None]:
    parsed = urlparse(mongo_connection_url)
    db_name = (parsed.path or "/clubs").lstrip("/") or "clubs"
    query = parse_qs(parsed.query)
    auth_source = query.get("authSource", ["admin"])[0]
    admin_url = f"{parsed.scheme}://{parsed.netloc}/?authSource={auth_source}"
    client = MongoClient(admin_url)
    client.drop_database(db_name)
    yield
    client.drop_database(db_name)
    client.close()


@pytest.fixture(autouse=True, scope="session")
def use_test_settings(mongo_connection_url: str) -> Iterator[None]:
    base_settings_path = _REPO_ROOT / "settings.test.yaml"
    with open(base_settings_path, encoding="utf-8") as file:
        settings_payload = yaml.safe_load(file)
    settings_payload["clubs_service"]["mongo"]["uri"] = mongo_connection_url
    loaded = config_root_schema.Settings.model_validate(settings_payload)

    previous_load_root_settings = config_root_schema.load_root_settings

    def fake_load_root_settings(path: Path | None = None) -> config_root_schema.Settings:
        _ = path
        return loaded

    config_root_schema.load_root_settings = fake_load_root_settings
    _sync_loaded_service_settings(loaded)
    assert loaded.maps_service.environment == "testing"
    assert loaded.clubs_service is not None
    assert loaded.clubs_service.environment == "testing"
    assert loaded.clubs_service.mongo.uri.get_secret_value() == mongo_connection_url
    assert loaded.student_affairs_service is not None
    assert loaded.student_affairs_service.environment == "testing"
    yield
    config_root_schema.load_root_settings = previous_load_root_settings


@pytest.fixture
def inh_accounts_mock_users() -> dict[str, dict[str, Any]]:
    now = datetime.datetime.now(datetime.UTC).isoformat()
    return {
        "superadmin-1": {
            "id": "superadmin-1",
            "innopolis_info": {
                "email": "admin@innopolis.university",
                "name": "Test Super Admin",
                "is_student": False,
                "is_staff": True,
                "is_college": False,
                "updated_at": now,
            },
            "innohassle_admin": True,
        },
        "test-user-1": {
            "id": "test-user-1",
            "innopolis_info": {
                "email": "test-user-1@innopolis.university",
                "name": "Test User One",
                "is_student": True,
                "is_staff": False,
                "is_college": False,
                "updated_at": now,
            },
            "telegram_info": {
                "id": 1001,
                "first_name": "Test",
                "last_name": "One",
                "username": "test_user_one",
                "updated_at": now,
            },
            "innohassle_admin": False,
        },
    }


@pytest.fixture(scope="session")
def jwt_keypair() -> tuple[RSAKey, RSAKey]:
    private_key_obj = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key_obj.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = private_key_obj.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return RSAKey.import_key(private_pem), RSAKey.import_key(public_pem)


@pytest.fixture
def make_user_token(jwt_keypair: tuple[RSAKey, RSAKey]) -> MakeUserToken:
    private_key, _ = jwt_keypair

    def _make(uid: str, email: str, telegram_id: int | None = None, expires_in_seconds: int = 3600) -> str:
        now = int(datetime.datetime.now(datetime.UTC).timestamp())
        claims: dict[str, Any] = {
            "uid": uid,
            "email": email,
            "iat": now,
            "exp": now + expires_in_seconds,
        }
        if telegram_id is not None:
            claims["telegram_id"] = telegram_id
        token = jwt.encode({"alg": "RS256", "kid": "public"}, claims, private_key)
        return token.decode() if isinstance(token, bytes) else token

    return _make


@pytest.fixture(autouse=True)
def mock_inh_accounts_http(
    inh_accounts_mock_users: dict[str, dict[str, Any]],
    jwt_keypair: tuple[RSAKey, RSAKey],
) -> Iterator[None]:
    _, public_key = jwt_keypair
    api_url = inh_accounts.api_url.rstrip("/")
    jwks_public_key = {**public_key.as_dict(private=False), "kid": inh_accounts.PUBLIC_KID}

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as respx_mock:
        respx_mock.get(f"{api_url}/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json={"keys": [jwks_public_key]})
        )

        def _find_by_email(email: str) -> dict[str, Any] | None:
            return next(
                (user for user in inh_accounts_mock_users.values() if user["innopolis_info"]["email"] == email), None
            )

        def _find_by_telegram_id(telegram_id: int) -> dict[str, Any] | None:
            return next(
                (
                    user
                    for user in inh_accounts_mock_users.values()
                    if user.get("telegram_info") and user["telegram_info"]["id"] == telegram_id
                ),
                None,
            )

        def _resp_for_user(user: dict[str, Any] | None) -> httpx.Response:
            if user is None:
                return httpx.Response(404, json={"detail": "Not found"})
            return httpx.Response(200, json=user)

        def _get_by_id(request: httpx.Request) -> httpx.Response:
            user_id = request.url.path.rsplit("/", 1)[-1]
            return _resp_for_user(inh_accounts_mock_users.get(user_id))

        def _get_by_email(request: httpx.Request) -> httpx.Response:
            email = unquote(request.url.path.rsplit("/", 1)[-1])
            return _resp_for_user(_find_by_email(email))

        def _get_by_telegram_id(request: httpx.Request) -> httpx.Response:
            telegram_id = int(request.url.path.rsplit("/", 1)[-1])
            return _resp_for_user(_find_by_telegram_id(telegram_id))

        def _bulk_by_id(request: httpx.Request) -> httpx.Response:
            user_ids = json.loads(request.content.decode() or "[]")
            payload = {user_id: inh_accounts_mock_users.get(user_id) for user_id in user_ids}
            return httpx.Response(200, json=payload)

        respx_mock.get(url__regex=rf"{re.escape(api_url)}/users/by-id/.+").mock(side_effect=_get_by_id)
        respx_mock.get(url__regex=rf"{re.escape(api_url)}/users/by-innomail/.+").mock(side_effect=_get_by_email)
        respx_mock.get(url__regex=rf"{re.escape(api_url)}/users/by-telegram-id/.+").mock(
            side_effect=_get_by_telegram_id
        )
        respx_mock.post(f"{api_url}/users/by-id/get-bulk").mock(side_effect=_bulk_by_id)

        yield
