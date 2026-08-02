import base64
import binascii
import datetime as dtm
import hashlib
import hmac
import json

from pydantic import BaseModel, ValidationError

from src.schedule_assistant.config import settings


class PreferenceTokenPayload(BaseModel):
    instructor_id: str
    exp: int


def _to_base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _from_base64url(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _secret_bytes() -> bytes:
    return settings.preference_link_secret.get_secret_value().encode("utf-8")


def _sign(data: str) -> bytes:
    return hmac.new(_secret_bytes(), data.encode("utf-8"), hashlib.sha256).digest()


def sign_preference_token(payload: PreferenceTokenPayload) -> str:
    payload_json = json.dumps(
        payload.model_dump(),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    payload_b64 = _to_base64url(payload_json)
    signature_b64 = _to_base64url(_sign(payload_b64))
    return f"{payload_b64}.{signature_b64}"


def verify_preference_token(token: str) -> PreferenceTokenPayload | None:
    try:
        payload_b64, signature_b64 = token.split(".", maxsplit=1)
        expected = _to_base64url(_sign(payload_b64))
        if not hmac.compare_digest(signature_b64, expected):
            return None
        payload = PreferenceTokenPayload.model_validate(json.loads(_from_base64url(payload_b64)))
    except ValueError, json.JSONDecodeError, binascii.Error, ValidationError:
        return None

    if payload.exp < int(dtm.datetime.now(dtm.UTC).timestamp()):
        return None
    return payload
