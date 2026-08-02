__all__ = ["SignaturePayload", "sign_payload", "verify_signature"]

import base64
import binascii
import hashlib
import hmac
import json

from src.forms.config import settings
from src.forms.modules.links.schemas import SignaturePayload


def _to_base64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _from_base64url(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(data: str) -> bytes:
    secret = settings.links.signature_secret.get_secret_value().encode("utf-8")
    return hmac.new(secret, data.encode("utf-8"), hashlib.sha256).digest()


def sign_payload(payload: SignaturePayload) -> str:
    payload_json = json.dumps(payload.model_dump(), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_b64 = _to_base64url(payload_json)
    signature_b64 = _to_base64url(_sign(payload_b64))
    return f"{payload_b64}.{signature_b64}"


def verify_signature(signature: str) -> SignaturePayload | None:
    try:
        payload_b64, signature_b64 = signature.split(".", maxsplit=1)
        expected_signature = _to_base64url(_sign(payload_b64))
        if not hmac.compare_digest(signature_b64, expected_signature):
            return None

        payload_json = _from_base64url(payload_b64)
        payload = json.loads(payload_json)
        return SignaturePayload.model_validate(payload)
    except ValueError, json.JSONDecodeError, binascii.Error:
        return None
