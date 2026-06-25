from src.forms.modules.links.schemas import SignaturePayload
from src.forms.modules.links.signature import sign_payload, verify_signature


def test_sign_verify_roundtrip():
    payload = SignaturePayload(
        email="user@innopolis.university",
        fio="Test User",
        telegram="@test_user",
    )
    signed = sign_payload(payload)
    verified = verify_signature(signed)
    assert verified == payload


def test_verify_tampered_signature_returns_none():
    payload = SignaturePayload(email="a@b.c", fio="Name", telegram="")
    signed = sign_payload(payload)
    payload_b64, signature_b64 = signed.split(".", maxsplit=1)
    tampered = f"{payload_b64}.{signature_b64[:-1]}x"
    assert verify_signature(tampered) is None


def test_verify_malformed_not_a_jwt():
    assert verify_signature("not-a-jwt") is None


def test_verify_malformed_missing_dot():
    assert verify_signature("onlyonepart") is None


def test_verify_malformed_bad_base64():
    assert verify_signature("!!!.!!!") is None
