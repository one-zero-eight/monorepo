import datetime as dtm

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from joserfc import jwt

from src.inh_accounts_sdk import inh_accounts
from src.schedule.dependencies import verify_parser, verify_parser_or_admin
from src.schedule.exceptions import ForbiddenException, IncorrectCredentialsException


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scope", "allowed"),
    [
        ("parser", True),
        ("users parser sport", True),
        ("parser users", True),
        ("users", False),
        ("parser-extra", False),
        ("", False),
    ],
)
async def test_parser_permissions_require_exact_scope(jwt_keypair, scope, allowed):
    await inh_accounts.update_key_set()
    private_key, _ = jwt_keypair
    now = int(dtm.datetime.now(dtm.UTC).timestamp())
    sub = "service" if allowed else "parser"
    token = jwt.encode({"alg": "RS256"}, {"sub": sub, "scope": scope, "iat": now, "exp": now + 3600}, private_key)
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    if allowed:
        assert verify_parser(bearer) is True
        assert await verify_parser_or_admin(bearer) is True
    else:
        with pytest.raises(IncorrectCredentialsException) as error:
            verify_parser(bearer)
        assert error.value.status_code == 401
        with pytest.raises(IncorrectCredentialsException) as error:
            await verify_parser_or_admin(bearer)
        assert error.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize("uid", ["superadmin-1", "test-user-1"])
async def test_parser_or_admin_preserves_user_admin_check(make_user_token, uid):
    await inh_accounts.update_key_set()
    email = "admin@innopolis.university" if uid == "superadmin-1" else "test-user-1@innopolis.university"
    bearer = HTTPAuthorizationCredentials(scheme="Bearer", credentials=make_user_token(uid=uid, email=email))

    if uid == "superadmin-1":
        assert await verify_parser_or_admin(bearer) is True
    else:
        with pytest.raises(ForbiddenException) as error:
            await verify_parser_or_admin(bearer)
        assert error.value.status_code == 403
