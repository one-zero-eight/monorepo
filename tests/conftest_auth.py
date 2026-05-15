import datetime as dtm
import json
import re
from collections.abc import Iterator
from typing import Any, Protocol
from urllib.parse import unquote

import httpx
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwt
from joserfc.jwk import RSAKey


class MakeUserToken(Protocol):
    def __call__(
        self,
        uid: str,
        email: str,
        telegram_id: int | None = None,
        expires_in_seconds: int = 3600,
    ) -> str: ...


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


@pytest.fixture(scope="session")
def make_user_token(jwt_keypair: tuple[RSAKey, RSAKey]) -> MakeUserToken:
    private_key, _ = jwt_keypair

    def _make(
        uid: str,
        email: str,
        telegram_id: int | None = None,
        expires_in_seconds: int = 3600,
    ) -> str:
        now = int(dtm.datetime.now(dtm.UTC).timestamp())

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


@pytest.fixture(scope="session")
def auth_header_factory(make_user_token: MakeUserToken):
    def _make(uid: str, email: str, expires_in_seconds: int = 3600) -> dict[str, str]:
        token = make_user_token(
            uid=uid,
            email=email,
            expires_in_seconds=expires_in_seconds,
        )

        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest.fixture(scope="session")
def superadmin_headers(auth_header_factory):
    return auth_header_factory("superadmin-1", "admin@innopolis.university")


@pytest.fixture(scope="session")
def user_headers(auth_header_factory):
    return auth_header_factory("test-user-1", "test-user-1@innopolis.university")


@pytest.fixture(scope="session")
def inh_accounts_mock_users() -> dict[str, dict[str, Any]]:
    now = dtm.datetime.now(dtm.UTC).isoformat()

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


@pytest.fixture(autouse=True, scope="session")
def mock_inh_accounts_http(
    inh_accounts_mock_users: dict[str, dict[str, Any]],
    jwt_keypair: tuple[RSAKey, RSAKey],
) -> Iterator[None]:
    from src.inh_accounts_sdk import inh_accounts

    _, public_key = jwt_keypair

    api_url = inh_accounts.api_url.rstrip("/")
    jwks_public_key = {
        **public_key.as_dict(private=False),
        "kid": inh_accounts.PUBLIC_KID,
    }

    def find_by_email(email: str) -> dict[str, Any] | None:
        return next(
            (user for user in inh_accounts_mock_users.values() if user["innopolis_info"]["email"] == email),
            None,
        )

    def find_by_telegram_id(telegram_id: int) -> dict[str, Any] | None:
        return next(
            (
                user
                for user in inh_accounts_mock_users.values()
                if user.get("telegram_info") and user["telegram_info"]["id"] == telegram_id
            ),
            None,
        )

    def response_for_user(user: dict[str, Any] | None) -> httpx.Response:
        if user is None:
            return httpx.Response(404, json={"detail": "Not found"})

        return httpx.Response(200, json=user)

    def get_by_id(request: httpx.Request) -> httpx.Response:
        user_id = request.url.path.rsplit("/", 1)[-1]
        return response_for_user(inh_accounts_mock_users.get(user_id))

    def get_by_email(request: httpx.Request) -> httpx.Response:
        email = unquote(request.url.path.rsplit("/", 1)[-1])
        return response_for_user(find_by_email(email))

    def get_by_telegram_id(request: httpx.Request) -> httpx.Response:
        telegram_id = int(request.url.path.rsplit("/", 1)[-1])
        return response_for_user(find_by_telegram_id(telegram_id))

    def bulk_by_id(request: httpx.Request) -> httpx.Response:
        user_ids = json.loads(request.content.decode() or "[]")
        payload = {user_id: inh_accounts_mock_users.get(user_id) for user_id in user_ids}

        return httpx.Response(200, json=payload)

    with respx.mock(assert_all_mocked=True, assert_all_called=False) as respx_mock:
        respx_mock.get(f"{api_url}/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json={"keys": [jwks_public_key]})
        )

        respx_mock.get(url__regex=rf"{re.escape(api_url)}/users/by-id/.+").mock(side_effect=get_by_id)
        respx_mock.get(url__regex=rf"{re.escape(api_url)}/users/by-innomail/.+").mock(side_effect=get_by_email)
        respx_mock.get(url__regex=rf"{re.escape(api_url)}/users/by-telegram-id/.+").mock(side_effect=get_by_telegram_id)
        respx_mock.post(f"{api_url}/users/by-id/get-bulk").mock(side_effect=bulk_by_id)

        yield
