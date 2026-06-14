from beanie import PydanticObjectId

from src.common_pydantic import BaseSchema
from src.inh_accounts_sdk import UserTokenData


class CreateUser(BaseSchema):
    innohassle_id: str


class ViewUser(BaseSchema):
    id: PydanticObjectId
    innohassle_id: str


class UserAuthData(BaseSchema):
    user_id: PydanticObjectId | None
    user_token_data: UserTokenData
