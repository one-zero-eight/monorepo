"""
Manage Yandex Forms links and generate signed prefilled URLs.
"""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from nanoid import generate
from pymongo.errors import DuplicateKeyError

from src.dependencies import INH_TOKEN_AUTH
from src.forms.modules.links.repository import link_repository
from src.forms.modules.links.schemas import (
    CreateLink,
    SignaturePayload,
    VerifySignatureRequest,
    VerifySignatureResponse,
    ViewLink,
    ViewLinksItem,
    ViewResolvedLink,
)
from src.forms.modules.links.signature import sign_payload, verify_signature
from src.inh_accounts_sdk import inh_accounts

router = APIRouter(
    prefix="/links",
    tags=["Links"],
    route_class=AutoDeriveResponsesAPIRoute,
)

ALLOWED_HOSTS = {
    "forms.yandex.ru",
    "forms.yandex.com",
    "forms.yandex.by",
    "forms.yandex.kz",
    "forms.yandex.com.tr",
}
ALLOWED_PATH_RE = re.compile(r"^/(u|cloud)/[0-9a-f]+$")


def _validate_yandex_forms_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"}:
        raise HTTPException(status_code=422, detail="Only http/https URLs are allowed")
    if not parsed.hostname or parsed.hostname not in ALLOWED_HOSTS:
        raise HTTPException(status_code=422, detail="URL host is not allowed")
    path = parsed.path.rstrip("/")
    if not ALLOWED_PATH_RE.match(path):
        raise HTTPException(status_code=422, detail="URL path must start with /u/ or /cloud/")

    return f"https://forms.yandex.ru{path}"


def _build_prefilled_url(base_url: str, payload: SignaturePayload, signature: str) -> str:
    parsed = urlsplit(base_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_params.update(
        {
            "email": payload.email,
            "fio": payload.fio,
            "telegram": payload.telegram,
            "s": signature,
        }
    )
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            urlencode(query_params),
            parsed.fragment,
        )
    )


@router.post("", responses={200: {"description": "Short link created"}})
async def create_link(link: CreateLink, auth: INH_TOKEN_AUTH) -> ViewLink:
    normalized_url = _validate_yandex_forms_url(link.form_url)

    existing_link = await link_repository.read_by_owner_and_form_url(
        owner_innohassle_id=auth.innohassle_id,
        form_url=normalized_url,
    )
    if existing_link is not None:
        return ViewLink(slug=existing_link.slug, short_path=f"/links/{existing_link.slug}")

    for _ in range(5):
        slug = generate(size=10)
        try:
            await link_repository.create(
                link=CreateLink(form_url=normalized_url),
                slug=slug,
                owner_innohassle_id=auth.innohassle_id,
            )
            return ViewLink(slug=slug, short_path=f"/links/{slug}")
        except DuplicateKeyError:
            existing_link = await link_repository.read_by_owner_and_form_url(
                owner_innohassle_id=auth.innohassle_id,
                form_url=normalized_url,
            )
            if existing_link is not None:
                return ViewLink(slug=existing_link.slug, short_path=f"/links/{existing_link.slug}")
            continue

    raise HTTPException(status_code=500, detail="Failed to generate unique slug")


@router.get("", responses={200: {"description": "Current user links"}})
async def get_links(auth: INH_TOKEN_AUTH) -> list[ViewLinksItem]:
    links = await link_repository.read_all_by_owner(owner_innohassle_id=auth.innohassle_id)
    return [ViewLinksItem(slug=link.slug, form_url=link.form_url, created_at=link.created_at) for link in links]


@router.delete("/{slug}", responses={200: {"description": "Link deleted"}})
async def delete_link(slug: str, auth: INH_TOKEN_AUTH) -> None:
    deleted = await link_repository.delete_by_slug_and_owner(slug=slug, owner_innohassle_id=auth.innohassle_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Link not found")


@router.get("/{slug}", responses={200: {"description": "Resolved signed Yandex form URL"}})
async def resolve_link(slug: str, auth: INH_TOKEN_AUTH) -> ViewResolvedLink:
    link = await link_repository.read_by_slug(slug)
    if link is None:
        raise HTTPException(status_code=404, detail="Link not found")

    user = await inh_accounts.get_user(innohassle_id=auth.innohassle_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    email = auth.email or ""
    fio = ""
    telegram = ""

    if user.innopolis_info is not None:
        email = user.innopolis_info.email or email
        fio = user.innopolis_info.name or ""
    if user.telegram_info is not None and user.telegram_info.username:
        telegram = f"@{user.telegram_info.username}"

    payload = SignaturePayload(email=email, fio=fio, telegram=telegram)
    signature = sign_payload(payload)
    resolved_url = _build_prefilled_url(link.form_url, payload, signature)

    return ViewResolvedLink(url=resolved_url)


@router.post("/verify", responses={200: {"description": "Signature verification result"}})
async def verify_link_signature(request: VerifySignatureRequest) -> VerifySignatureResponse:
    payload = verify_signature(request.s)
    if payload is None:
        return VerifySignatureResponse(valid=False)
    return VerifySignatureResponse(valid=True, payload=payload)
