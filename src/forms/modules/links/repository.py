__all__ = ["link_repository"]

from src.forms.modules.links.schemas import CreateLink
from src.forms.mongo import Link


class LinkRepository:
    async def create(self, link: CreateLink, slug: str, owner_innohassle_id: str) -> Link:
        created = Link(
            slug=slug,
            form_url=link.form_url,
            owner_innohassle_id=owner_innohassle_id,
        )
        return await created.insert()

    async def read_by_slug(self, slug: str) -> Link | None:
        return await Link.find_one(Link.slug == slug)

    async def read_by_owner_and_form_url(self, owner_innohassle_id: str, form_url: str) -> Link | None:
        return await Link.find_one(
            Link.owner_innohassle_id == owner_innohassle_id,
            Link.form_url == form_url,
        )

    async def read_all_by_owner(self, owner_innohassle_id: str) -> list[Link]:
        return await Link.find(Link.owner_innohassle_id == owner_innohassle_id).sort("-created_at").to_list()

    async def delete_by_slug_and_owner(self, slug: str, owner_innohassle_id: str) -> bool:
        link = await Link.find_one(Link.slug == slug, Link.owner_innohassle_id == owner_innohassle_id)
        if link is None:
            return False
        await link.delete()
        return True


link_repository: LinkRepository = LinkRepository()
