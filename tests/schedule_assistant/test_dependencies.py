import pytest
from fastapi import HTTPException

from src.inh_accounts_sdk import UserTokenData
from src.schedule_assistant.dependencies import is_moderator_email, verify_moderator_dep


@pytest.mark.parametrize(
    ("email", "moderators", "expected"),
    [
        ("alice@innopolis.university", ["alice@innopolis.university"], True),
        ("Alice@Innopolis.University", ["alice@innopolis.university"], True),
        ("bob@innopolis.university", ["alice@innopolis.university"], False),
    ],
)
def test_is_moderator_email(email: str, moderators: list[str], expected: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", moderators)
    assert is_moderator_email(email) is expected


@pytest.mark.asyncio
async def test_verify_moderator_dep_rejects_non_moderator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails", ["moderator@innopolis.university"]
    )
    user_and_token = (UserTokenData(innohassle_id="1", email="user@innopolis.university"), "token")

    with pytest.raises(HTTPException) as exc_info:
        await verify_moderator_dep(user_and_token)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_verify_moderator_dep_allows_moderator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "src.schedule_assistant.dependencies.settings.moderator_emails", ["moderator@innopolis.university"]
    )
    user_and_token = (UserTokenData(innohassle_id="1", email="moderator@innopolis.university"), "token")

    result = await verify_moderator_dep(user_and_token)

    assert result == user_and_token
