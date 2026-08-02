import datetime as dtm

from src.common_pydantic import BaseSchema


class CreateLink(BaseSchema):
    form_url: str


class ViewLink(BaseSchema):
    slug: str
    short_path: str


class ViewLinksItem(BaseSchema):
    slug: str
    form_url: str
    created_at: dtm.datetime


class ViewResolvedLink(BaseSchema):
    url: str


class SignaturePayload(BaseSchema):
    email: str
    fio: str
    telegram: str


class VerifySignatureRequest(BaseSchema):
    s: str


class VerifySignatureResponse(BaseSchema):
    valid: bool
    payload: SignaturePayload | None = None
