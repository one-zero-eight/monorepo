import datetime as dtm

from fastapi import APIRouter, HTTPException, Request
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from joserfc import jwk, jwt

from src.dependencies import INH_TOKEN_AUTH
from src.inh_accounts_sdk import inh_accounts

from .config import settings

router = APIRouter(route_class=AutoDeriveResponsesAPIRoute)

omnidesk_default_redirect_to = f"{settings.omnidesk.base_url}/user/cases/"
omnidesk_jwt_access_base_url = f"{settings.omnidesk.base_url}/access/jwt"


@router.post("/sso/generate-link")
async def generate_signin_link(
    request: Request,
    auth: INH_TOKEN_AUTH,
    return_to: str | None = None,
) -> str:
    """
    Create a link for user authentication.
    https://support.omnidesk.ru/knowledge_base/item/54180
    """

    # Get user info
    accounts_user = await inh_accounts.get_user(innohassle_id=auth.innohassle_id)
    if accounts_user is None:
        raise HTTPException(status_code=400, detail="User not found")
    # Build JWT
    issued_at = dtm.datetime.now(dtm.UTC)
    expire = issued_at + dtm.timedelta(minutes=30)
    payload: dict = {
        "iat": issued_at,
        "exp": expire,
        "email": auth.email,
        "name": accounts_user.innopolis_info.name,
        "external_id": auth.innohassle_id,  # Should we add this?
    }
    key = jwk.import_key(settings.omnidesk.jwt_marker.get_secret_value(), "oct")
    encoded_jwt = jwt.encode({"alg": "HS256"}, payload, key)

    # Receive redirect link from Omnidesk
    query_params = {"jwt": encoded_jwt, "return_to": return_to or omnidesk_default_redirect_to}
    resp = await request.app.state.httpx_client.get(omnidesk_jwt_access_base_url, params=query_params)
    resp.raise_for_status()
    return resp.text
