from typing import cast

from beanie import Document, View

from src.storages.mongo.club import Club
from src.storages.mongo.user import User

document_models = cast(list[type[Document] | type[View] | str], [Club, User])
