from src.common_pydantic import BaseSchema
from src.inh_accounts_sdk import UserSchema, inh_accounts


class Leader(BaseSchema):
    """Club leader"""

    innohassle_id: str
    "ID of the InNoHassle Accounts user"
    name: str | None
    "Full name (or None if unknown)"
    email: str | None
    "Innomail (or None if unknown)"
    telegram_alias: str | None
    "Telegram alias (or None if unknown)"


def leader_from_innohassle_user(user: UserSchema) -> Leader:
    return Leader(
        innohassle_id=user.id,
        name=user.innopolis_info.name if user.innopolis_info else None,
        email=user.innopolis_info.email if user.innopolis_info else None,
        telegram_alias=user.telegram_info.username if user.telegram_info else None,
    )


async def read_by_innohassle_id(innohassle_id: str) -> Leader | None:
    leader_data = await inh_accounts.get_user(innohassle_id=innohassle_id)
    if not leader_data:
        return None
    return leader_from_innohassle_user(leader_data)


async def read_many_by_innohassle_ids(innohassle_ids: list[str]) -> dict[str, Leader | None]:
    user_infos = await inh_accounts.get_users(innohassle_ids=innohassle_ids)
    return {k: leader_from_innohassle_user(user) if user else None for k, user in user_infos.items()}
