import pytest
from beanie import PydanticObjectId
from fastapi import HTTPException

from src.guard.config import settings
from src.guard.modules.google_.constants import FileTypes
from src.guard.modules.google_.service import (
    create_google_file,
    generate_join_link,
    verify_file_ownership,
)
from tests.guard.constants import GUARD_AUTHOR_OBJECT_ID, GUARD_OTHER_OBJECT_ID


def test_generate_join_link():
    link = generate_join_link("abc123slug")
    assert link == f"{settings.base_url}/guard/google/files/abc123slug/join"


class _FileStub:
    author_id = PydanticObjectId(GUARD_AUTHOR_OBJECT_ID)


def test_verify_file_ownership_author_ok():
    verify_file_ownership(_FileStub(), GUARD_AUTHOR_OBJECT_ID)


def test_verify_file_ownership_other_user_forbidden():
    with pytest.raises(HTTPException) as exc:
        verify_file_ownership(_FileStub(), GUARD_OTHER_OBJECT_ID)
    assert exc.value.status_code == 403
    assert exc.value.detail == "You are not the author of this file"


def test_create_google_file_document_not_implemented():
    with pytest.raises(HTTPException) as exc:
        create_google_file(file_type=FileTypes.DOCUMENT, title="Doc")
    assert exc.value.status_code == 501
