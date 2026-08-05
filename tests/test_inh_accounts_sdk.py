import base64
import datetime as dtm
import json
import logging
from unittest.mock import Mock

import httpx
import pytest
import respx

from src.inh_accounts_sdk import InNoHassleAccounts

_TEST_API_JWT = "token"


def _make_unsigned_jwt(*, exp: int | None) -> str:
    def b64(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    payload: dict = {"sub": "test"}
    if exp is not None:
        payload["exp"] = exp
    return f"{b64({'alg': 'none'})}.{b64(payload)}.sig"


def test_init_logs_warning_when_token_missing(caplog):
    logger = Mock(spec=logging.Logger)
    InNoHassleAccounts(api_url="https://example.test", api_jwt_token=None, logger=logger)
    logger.warning.assert_called_once()


def test_init_uses_default_logger_when_not_provided(monkeypatch):
    logger = Mock(spec=logging.Logger)
    with monkeypatch.context() as m:
        m.setattr(logging, "getLogger", lambda _name=None: logger)
        InNoHassleAccounts(api_url="https://example.test", api_jwt_token=None, logger=None)
        logger.warning.assert_called_once()


def test_init_warns_when_token_expires_within_14_days():
    logger = Mock(spec=logging.Logger)
    exp = int((dtm.datetime.now(dtm.UTC) + dtm.timedelta(days=7)).timestamp())
    InNoHassleAccounts(
        api_url="https://example.test",
        api_jwt_token=_make_unsigned_jwt(exp=exp),
        logger=logger,
    )
    assert logger.warning.call_count == 1
    msg = logger.warning.call_args.args[0]
    assert "expires in" in msg
    assert "generate-service-token" in msg


def test_init_warns_when_token_already_expired():
    logger = Mock(spec=logging.Logger)
    exp = int((dtm.datetime.now(dtm.UTC) - dtm.timedelta(days=1)).timestamp())
    InNoHassleAccounts(
        api_url="https://example.test",
        api_jwt_token=_make_unsigned_jwt(exp=exp),
        logger=logger,
    )
    assert logger.warning.call_count == 1
    assert "already expired" in logger.warning.call_args.args[0]


def test_init_does_not_warn_when_token_far_from_expiry():
    logger = Mock(spec=logging.Logger)
    exp = int((dtm.datetime.now(dtm.UTC) + dtm.timedelta(days=60)).timestamp())
    InNoHassleAccounts(
        api_url="https://example.test",
        api_jwt_token=_make_unsigned_jwt(exp=exp),
        logger=logger,
    )
    logger.warning.assert_not_called()


def test_get_public_key_raises_when_keyset_not_initialized():
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=_TEST_API_JWT)
    accounts.key_set = None
    with pytest.raises(RuntimeError, match="initialized by `update_key_set`"):
        accounts.get_public_key()


def test_get_public_key_raises_when_public_kid_missing():
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=_TEST_API_JWT)
    accounts.key_set = {"keys": [{"kid": "other"}]}
    with pytest.raises(RuntimeError, match="Public key with kid='public' is missing"):
        accounts.get_public_key()


def test_decode_user_token_returns_none_when_required_claims_missing(monkeypatch):
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=_TEST_API_JWT)
    monkeypatch.setattr(accounts, "_get_jwt_claims", lambda _token: {"uid": "u-only"})
    assert accounts.decode_user_token("token") is None


def test_decode_user_token_mock_mode_accepts_json_user_token_data():
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=_TEST_API_JWT, mock=True)
    raw = '{"innohassle_id":"u1","email":"u1@innopolis.university","telegram_id":99}'
    data = accounts.decode_user_token(raw)
    assert data is not None
    assert data.innohassle_id == "u1"
    assert data.email == "u1@innopolis.university"
    assert data.telegram_id == 99


def test_decode_user_token_mock_mode_returns_none_when_json_invalid():
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=_TEST_API_JWT, mock=True)
    assert accounts.decode_user_token('{"innohassle_id":"only"}') is None


@pytest.mark.asyncio
async def test_update_key_set_skipped_when_mock():
    accounts = InNoHassleAccounts(api_url="https://unreachable.invalid", api_jwt_token=None, mock=True)
    await accounts.update_key_set()
    assert accounts.key_set == {"keys": []}


def test_get_authorized_client_raises_without_api_token():
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=None)
    with pytest.raises(ValueError, match="API JWT token is not set"):
        accounts.get_authorized_client()


@pytest.mark.asyncio
async def test_http_client_is_reused_across_requests():
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=_TEST_API_JWT)
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://example.test/users/by-id/u-1").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        respx_mock.get("https://example.test/users/by-id/u-2").mock(
            return_value=httpx.Response(404, json={"detail": "Not found"})
        )
        client_before = accounts.get_authorized_client()
        await accounts.get_user(innohassle_id="u-1")
        await accounts.get_user(innohassle_id="u-2")
        assert accounts.get_authorized_client() is client_before
    await accounts.aclose()


@pytest.mark.asyncio
async def test_get_user_can_fetch_by_telegram_id():
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=_TEST_API_JWT)
    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://example.test/users/by-telegram-id/1001").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": "u-1",
                    "innopolis_info": {
                        "email": "u1@innopolis.university",
                        "name": "U One",
                        "is_student": True,
                        "is_staff": False,
                        "is_college": False,
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    },
                    "telegram_info": {
                        "id": 1001,
                        "first_name": "U",
                        "last_name": "One",
                        "username": "uone",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    },
                    "innohassle_admin": False,
                },
            )
        )
        user = await accounts.get_user(telegram_id=1001)
    assert user is not None
    assert user.id == "u-1"


@pytest.mark.asyncio
async def test_get_user_raises_on_non_404_http_error():
    accounts = InNoHassleAccounts(api_url="https://example.test", api_jwt_token=_TEST_API_JWT)
    request = httpx.Request("GET", "https://example.test/users/by-id/u-1")
    response = httpx.Response(500, request=request)

    with respx.mock(assert_all_called=True) as respx_mock:
        respx_mock.get("https://example.test/users/by-id/u-1").mock(return_value=response)
        with pytest.raises(httpx.HTTPStatusError):
            await accounts.get_user(innohassle_id="u-1")
