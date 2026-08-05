# This file should be synced with:
# https://github.com/one-zero-eight/accounts/blob/main/inh_accounts_sdk.py

import base64
import datetime as dtm
import json
import logging
from logging import Logger
from typing import Any

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import RSAKey
from joserfc.jwt import JWTClaimsRegistry
from pydantic import BaseModel, SecretStr

_TOKEN_EXPIRY_WARN_DAYS = 14


class TelegramInfo(BaseModel):
    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    updated_at: dtm.datetime


class InnopolisInfo(BaseModel):
    email: str
    name: str | None = None
    is_student: bool = False
    is_staff: bool = False
    is_college: bool = False
    updated_at: dtm.datetime


class UserSchema(BaseModel):
    id: str
    innopolis_info: InnopolisInfo
    telegram_info: TelegramInfo | None = None
    innohassle_admin: bool = False


class UserTokenData(BaseModel):
    innohassle_id: str
    "InNoHassle Accounts ID"
    email: str
    "Innopolis email (@innopolis.university or @innopolis.ru)"
    telegram_id: int | None = None
    "User's Telegram ID connected to InNoHassle Accounts"


class RoomTvTokenData(BaseModel):
    room_id: str
    "Room ID in Room Booking service"


def _peek_jwt_claims(token: str) -> dict[str, Any] | None:
    """Read JWT payload without verifying signature (for local expiry checks)."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except ValueError, json.JSONDecodeError:
        return None


class InNoHassleAccounts:
    api_url: str
    api_jwt_token: str | SecretStr | None
    mock: bool
    PUBLIC_KID = "public"
    key_set: dict[str, Any] | None = None
    _http: httpx.AsyncClient | None = None

    def __init__(
        self,
        api_url: str = "https://api.innohassle.ru/accounts/v0",
        api_jwt_token: str | SecretStr | None = None,
        mock: bool = False,
        logger: Logger | None = None,
    ):
        self.api_url = api_url
        self.api_jwt_token = api_jwt_token
        self.mock = mock
        if logger is None:
            logger = logging.getLogger(__name__)
        self.logger = logger
        if self.api_jwt_token is None:
            self.logger.warning(
                "InNoHassle Accounts API JWT token is not set, you will not be able to call service endpoints that require authorization"
            )
        else:
            self._warn_if_api_jwt_expiring_soon()

    def _api_jwt_token_value(self) -> str | None:
        if self.api_jwt_token is None:
            return None
        if isinstance(self.api_jwt_token, SecretStr):
            return self.api_jwt_token.get_secret_value()
        return self.api_jwt_token

    def _warn_if_api_jwt_expiring_soon(self) -> None:
        token = self._api_jwt_token_value()
        if not token:
            return
        claims = _peek_jwt_claims(token)
        if claims is None:
            return
        exp = claims.get("exp")
        if exp is None:
            return
        try:
            expires_at = dtm.datetime.fromtimestamp(exp, tz=dtm.UTC)
        except TypeError, OSError, ValueError:
            return
        remaining = expires_at - dtm.datetime.now(dtm.UTC)
        if remaining <= dtm.timedelta(days=_TOKEN_EXPIRY_WARN_DAYS):
            if remaining.total_seconds() <= 0:
                self.logger.warning(
                    "InNoHassle Accounts API JWT token has already expired at %s. "
                    "Regenerate via /tokens/generate-service-token",
                    expires_at.isoformat(),
                )
            else:
                self.logger.warning(
                    "InNoHassle Accounts API JWT token expires in %s days (at %s). "
                    "Regenerate via /tokens/generate-service-token",
                    remaining.days,
                    expires_at.isoformat(),
                )

    def _ensure_http_client(self) -> httpx.AsyncClient:
        if self._http is None:
            headers: dict[str, str] = {}
            token = self._api_jwt_token_value()
            if token is not None:
                headers["Authorization"] = f"Bearer {token}"
            self._http = httpx.AsyncClient(base_url=self.api_url, headers=headers)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def update_key_set(self):
        if self.mock:
            self.key_set = {"keys": []}
            self.logger.warning("InNoHassle Accounts mock mode: JWKS fetch skipped")
            return
        self.logger.info("Updating key set for InNoHassle Accounts...")
        self.key_set = await self.get_key_set()
        self.logger.info("Key set updated successfully")

    def get_public_key(self) -> RSAKey:
        if self.key_set is None:
            raise RuntimeError("Key set should be initialized by `update_key_set`")
        key_data = next((key for key in self.key_set.get("keys", []) if key.get("kid") == self.PUBLIC_KID), None)
        if key_data is None:
            raise RuntimeError(f"Public key with kid={self.PUBLIC_KID!r} is missing in JWKS")
        return RSAKey.import_key(key_data)

    async def get_key_set(self) -> dict[str, Any]:
        client = self._ensure_http_client()
        response = await client.get("/.well-known/jwks.json")
        response.raise_for_status()
        return response.json()

    def decode_user_token(self, token: str) -> UserTokenData | None:
        """
        Decode generated by InnoHassle Accounts user JWT token and return user data.
        If token is invalid, return None.
        """
        if self.mock:
            raw = token.strip()
            if raw.startswith("{"):
                try:
                    return UserTokenData.model_validate_json(raw)
                except Exception:
                    self.logger.warning(f"Invalid mock Bearer JSON for UserTokenData: {raw}", exc_info=True)
                    return None
        try:
            payload = self._get_jwt_claims(token)
            innohassle_id: str | None = payload.get("uid")
            email: str | None = payload.get("email")
            telegram_id: int | None = payload.get("telegram_id")
            if innohassle_id is None or email is None:
                raise JoseError("Missing required claims: uid/email")
            return UserTokenData(
                innohassle_id=innohassle_id,
                email=email,
                telegram_id=telegram_id,
            )
        except JoseError:
            self.logger.warning("Invalid token", exc_info=True)
            return None

    def decode_room_tv_token(self, token: str) -> RoomTvTokenData | None:
        """
        Decode generated by InnoHassle Accounts Room TV JWT token and return room id.
        If token is invalid, return None.
        """
        if self.mock:
            raw = token.strip()
            if raw.startswith("{"):
                try:
                    return RoomTvTokenData.model_validate_json(raw)
                except Exception:
                    self.logger.warning(f"Invalid mock Bearer JSON for RoomTvTokenData: {raw}", exc_info=True)
                    return None
        try:
            payload = self._get_jwt_claims(token)
            if payload.get("aud") != "room-booking":
                self.logger.warning("Provided Room TV token has incorrect 'aud'")
                return None
            room_id: str | None = payload.get("room_id")
            if room_id is None:
                raise JoseError("Missing required claims: room_id")
            return RoomTvTokenData(room_id=room_id)
        except JoseError:
            self.logger.warning("Invalid token", exc_info=True)
            return None

    def get_authorized_client(self) -> httpx.AsyncClient:
        if self._api_jwt_token_value() is None:
            raise ValueError("API JWT token is not set")
        return self._ensure_http_client()

    def _get_jwt_claims(self, token: str) -> dict[str, Any]:
        pub_key = self.get_public_key()
        payload = jwt.decode(token, pub_key)
        claims = payload.claims
        JWTClaimsRegistry().validate(claims)
        return claims

    async def get_user(
        self,
        innohassle_id: str | None = None,
        email: str | None = None,
        telegram_id: int | None = None,
    ) -> UserSchema | None:
        """
        Get user by one of the provided identifiers.
        If multiple identifiers are provided, the first one that exists will be returned.
        """
        client = self.get_authorized_client()
        urls = []
        if innohassle_id:
            urls.append(f"/users/by-id/{innohassle_id}")
        if email:
            urls.append(f"/users/by-innomail/{email}")
        if telegram_id:
            urls.append(f"/users/by-telegram-id/{telegram_id}")
        for url in urls:
            response = await client.get(url)
            try:
                response.raise_for_status()
                return UserSchema.model_validate(response.json())
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    continue
                raise
        return None

    async def get_users(self, innohassle_ids: list[str]) -> dict[str, UserSchema | None]:
        """
        Get multiple users by ids.
        """
        client = self.get_authorized_client()
        response = await client.post("/users/by-id/get-bulk", json=innohassle_ids)
        response.raise_for_status()
        return {k: UserSchema.model_validate(v) if v else None for k, v in response.json().items()}

    async def get_sport_token(self, innohassle_id: str) -> str:
        client = self.get_authorized_client()
        response = await client.get("/tokens/generate-sport-token", params={"innohassle_id": innohassle_id})
        response.raise_for_status()
        return response.json()["access_token"]


# Project specific code follows
import src.logging_  # noqa: E402
from src.config_root_schema import load_root_settings  # noqa: E402

root_settings = load_root_settings()

if root_settings.accounts:
    inh_accounts: InNoHassleAccounts = InNoHassleAccounts(
        api_url=root_settings.accounts.api_url,
        api_jwt_token=root_settings.accounts.api_jwt_token,
        mock=root_settings.accounts.mock,
        logger=src.logging_.logger,
    )
else:
    raise ImportError("InNoHassle Accounts is not configured in ./settings.yaml")  # pragma: no cover
# ^
