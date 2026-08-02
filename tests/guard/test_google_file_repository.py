import pytest
from beanie import PydanticObjectId

from src.guard.modules.google_.exceptions import UserBannedException
from src.guard.modules.google_.repository import google_file_repository
from tests.guard.constants import GUARD_OTHER_OBJECT_ID


def test_create_file_and_get_by_slug(guard_portal, create_google_file):
    created = create_google_file()
    loaded = guard_portal.call(google_file_repository.get_by_slug, created.slug)
    assert loaded is not None
    assert loaded.file_id == "google-file-id-1"
    assert loaded.slug == created.slug


def test_join_user_to_file(guard_portal, create_google_file):
    created = create_google_file()
    other_id = PydanticObjectId(GUARD_OTHER_OBJECT_ID)

    async def _join():
        return await google_file_repository.join_user_to_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
            role="writer",
            permission_id="perm-join-1",
        )

    updated = guard_portal.call(_join)
    assert updated is not None
    assert len(updated.sso_joins) == 1
    assert updated.sso_joins[0].gmail == "joiner@gmail.com"
    assert updated.sso_joins[0].role == "writer"


def test_join_duplicate_gmail_is_idempotent(guard_portal, create_google_file):
    created = create_google_file()
    other_id = PydanticObjectId(GUARD_OTHER_OBJECT_ID)

    async def _join(permission_id: str):
        return await google_file_repository.join_user_to_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
            role="reader",
            permission_id=permission_id,
        )

    guard_portal.call(_join, "perm-1")
    again = guard_portal.call(_join, "perm-2")
    assert again is not None
    assert len(again.sso_joins) == 1


def test_join_raises_when_user_banned(guard_portal, create_google_file):
    created = create_google_file()
    other_id = PydanticObjectId(GUARD_OTHER_OBJECT_ID)

    async def _ban():
        await google_file_repository.ban_user_from_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
        )

    async def _join():
        await google_file_repository.join_user_to_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
            role="reader",
            permission_id="perm-1",
        )

    guard_portal.call(_ban)
    with pytest.raises(UserBannedException):
        guard_portal.call(_join)


def test_ban_user_from_file(guard_portal, create_google_file):
    created = create_google_file()
    other_id = PydanticObjectId(GUARD_OTHER_OBJECT_ID)

    async def _join():
        await google_file_repository.join_user_to_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
            role="reader",
            permission_id="perm-1",
        )

    async def _ban():
        return await google_file_repository.ban_user_from_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
        )

    guard_portal.call(_join)
    banned = guard_portal.call(_ban)
    assert banned is not None
    assert banned.sso_joins == []
    assert len(banned.sso_banned) == 1
    assert banned.sso_banned[0].user_id == other_id


def test_unban_user_from_file(guard_portal, create_google_file):
    created = create_google_file()
    other_id = PydanticObjectId(GUARD_OTHER_OBJECT_ID)

    async def _ban():
        await google_file_repository.ban_user_from_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
        )

    async def _unban():
        return await google_file_repository.unban_user_from_file(slug=created.slug, user_id=other_id)

    guard_portal.call(_ban)
    unbanned = guard_portal.call(_unban)
    assert unbanned is not None
    assert unbanned.sso_banned == []


def test_delete_by_slug(guard_portal, create_google_file):
    created = create_google_file()

    async def _delete():
        return await google_file_repository.delete_by_slug(created.slug)

    async def _get():
        return await google_file_repository.get_by_slug(created.slug)

    assert guard_portal.call(_delete) is True
    assert guard_portal.call(_get) is None


def test_update_user_role_and_default_role(guard_portal, create_google_file):
    created = create_google_file()
    other_id = PydanticObjectId(GUARD_OTHER_OBJECT_ID)

    async def _join():
        await google_file_repository.join_user_to_file(
            slug=created.slug,
            user_id=other_id,
            gmail="joiner@gmail.com",
            innomail="joiner@innopolis.university",
            role="reader",
            permission_id="perm-1",
        )

    async def _update_user_role():
        return await google_file_repository.update_user_role(created.slug, other_id, "writer")

    async def _update_default_role():
        return await google_file_repository.update_default_role(created.slug, "writer")

    guard_portal.call(_join)
    role_updated = guard_portal.call(_update_user_role)
    assert role_updated is not None
    assert role_updated.sso_joins[0].role == "writer"

    default_updated = guard_portal.call(_update_default_role)
    assert default_updated is not None
    assert default_updated.default_role == "writer"
