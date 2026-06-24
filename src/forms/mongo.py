__all__ = [
    "Link",
    "LinkSchema",
    "document_models",
]

import datetime as dtm
from typing import ClassVar

from pydantic import Field
from pymongo import IndexModel

from src.common_beanie import BeanieDocument
from src.common_pydantic import BaseSchema


class LinkSchema(BaseSchema):
    slug: str
    form_url: str
    owner_innohassle_id: str
    created_at: dtm.datetime


class Link(LinkSchema, BeanieDocument):
    created_at: dtm.datetime = Field(default_factory=lambda: dtm.datetime.now(tz=dtm.UTC))

    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [
            IndexModel("slug", unique=True),
            IndexModel("owner_innohassle_id"),
            IndexModel([("owner_innohassle_id", 1), ("form_url", 1)], unique=True),
        ]


document_models = [Link]
