import datetime as dtm
import random
from string import ascii_letters, digits

from beanie import PydanticObjectId

from src.guard.modules.google_.constants import SLUG_LENGTH
from src.guard.modules.google_.exceptions import UserBannedException
from src.guard.mongo import (
    GoogleFile,
    GoogleFileSSOBan,
    GoogleFileSSOJoin,
    GoogleFileType,
    GoogleFileUserRole,
    UserID,
)


def generate_slug():
    return "".join(random.choices(ascii_letters + digits, k=SLUG_LENGTH))  # noqa: S311


class GoogleFileRepository:
    async def create_file(
        self,
        author_id: UserID,
        default_role: GoogleFileUserRole,
        file_id: str,
        file_type: GoogleFileType,
        title: str,
        owner_gmail: str,
        owner_permission_id: str,
    ) -> GoogleFile:
        file = GoogleFile(
            author_id=author_id,
            default_role=default_role,
            file_id=file_id,
            file_type=file_type,
            slug=generate_slug(),
            title=title,
            owner_gmail=owner_gmail,
            owner_permission_id=owner_permission_id,
            sso_joins=[],
            sso_banned=[],
        )
        await file.save()
        return file

    async def get_by_file_id(self, file_id: str) -> GoogleFile | None:
        return await GoogleFile.find_one(GoogleFile.file_id == file_id)

    async def get_by_slug(self, slug: str) -> GoogleFile | None:
        return await GoogleFile.find_one(GoogleFile.slug == slug)

    async def get_by_author_id(self, author_id: str) -> list[GoogleFile]:
        return await GoogleFile.find(GoogleFile.author_id == PydanticObjectId(author_id)).to_list()

    async def join_user_to_file(
        self,
        slug: str,
        user_id: UserID,
        gmail: str,
        innomail: str,
        role: GoogleFileUserRole,
        permission_id: str | None = None,
    ):
        file = await self.get_by_slug(slug)
        if not file:
            return None

        if any(join.gmail == gmail for join in file.sso_joins):
            return file

        if any(ban.user_id == user_id for ban in file.sso_banned):
            raise UserBannedException(user_id=user_id)

        file.sso_joins.append(
            GoogleFileSSOJoin(
                user_id=user_id,
                gmail=gmail,
                innomail=innomail,
                role=role,
                joined_at=dtm.datetime.now(),  # noqa: DTZ005
                permission_id=permission_id,
            )
        )
        await file.save()
        return file

    async def remove_user_from_file(self, slug: str, user_id: UserID):
        file = await self.get_by_slug(slug)
        if not file:
            return None

        file.sso_joins = [join for join in file.sso_joins if str(join.user_id) != str(user_id)]
        await file.save()
        return file

    async def ban_user_from_file(self, slug: str, user_id: UserID, gmail: str, innomail: str):
        file = await self.get_by_slug(slug)
        if not file:
            return None

        file.sso_joins = [j for j in file.sso_joins if j.user_id != user_id]

        if any(ban.user_id == user_id for ban in file.sso_banned):
            await file.save()
            return file

        file.sso_banned.append(
            GoogleFileSSOBan(
                user_id=user_id,
                gmail=gmail,
                innomail=innomail,
                banned_at=dtm.datetime.now(),  # noqa: DTZ005
            )
        )
        await file.save()
        return file

    async def unban_user_from_file(self, slug: str, user_id: UserID):
        file = await self.get_by_slug(slug)
        if not file:
            return None

        if not any(ban.user_id == user_id for ban in file.sso_banned):
            return file

        file.sso_banned = [ban for ban in file.sso_banned if ban.user_id != user_id]
        await file.save()
        return file

    async def delete_by_slug(self, slug: str) -> bool:
        file = await self.get_by_slug(slug)
        if not file:
            return False
        await file.delete()
        return True

    async def update_file_title(self, slug: str, title: str) -> GoogleFile | None:
        file = await self.get_by_slug(slug)
        if not file:
            return None
        file.title = title
        await file.save()
        return file

    async def update_user_role(self, slug: str, user_id: UserID, role: GoogleFileUserRole) -> GoogleFile | None:
        file = await self.get_by_slug(slug)
        if not file:
            return None

        for join in file.sso_joins:
            if join.user_id == user_id:
                join.role = role
                await file.save()
                return file

        return None

    async def update_default_role(self, slug: str, role: GoogleFileUserRole) -> GoogleFile | None:
        file = await self.get_by_slug(slug)
        if not file:
            return None
        file.default_role = role
        await file.save()
        return file


google_file_repository = GoogleFileRepository()
