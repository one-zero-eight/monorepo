"""InNoHassle Clubs service REST client (authorized with a service API key)."""

import asyncio

import httpx

from src.common_pydantic import BaseSchema
from src.events.config import settings
from src.events.schemas import OwnedClub


class ClubInfo(BaseSchema):
    id: str
    title: str
    slug: str


class ClubsClient:
    def __init__(self, api_url: str, api_key: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def list_owned_clubs(self, innohassle_id: str) -> list[OwnedClub]:
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.get(f"{self._api_url}/clubs/owned-by/{innohassle_id}")
            response.raise_for_status()
            return [OwnedClub.model_validate(item) for item in response.json()]

    async def list_all_clubs(self) -> list[OwnedClub]:
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.get(f"{self._api_url}/clubs/")
            response.raise_for_status()
            return [OwnedClub(club_id=str(item["id"]), title=item["title"]) for item in response.json()]

    async def get_clubs(self, club_ids: set[str]) -> dict[str, ClubInfo]:
        """Fetch clubs by id; omitted ids were not found (404)."""
        if not club_ids:
            return {}

        async with httpx.AsyncClient(headers=self._headers) as client:

            async def fetch(club_id: str) -> tuple[str, ClubInfo | None]:
                response = await client.get(f"{self._api_url}/clubs/by-id/{club_id}")
                if response.status_code == 404:
                    return club_id, None
                response.raise_for_status()
                data = response.json()
                return club_id, ClubInfo(id=str(data["id"]), title=data["title"], slug=data["slug"])

            pairs = await asyncio.gather(*(fetch(club_id) for club_id in club_ids))
        return {club_id: club for club_id, club in pairs if club is not None}


clubs_client = ClubsClient(
    api_url=settings.clubs.api_url,
    api_key=settings.clubs.api_key.get_secret_value(),
)
