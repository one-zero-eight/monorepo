"""InNoHassle Clubs service adapter (authorized with a service API key)."""

import asyncio

import httpx

from src.clients.clubs import ApiError
from src.clients.clubs import ClubsClient as GeneratedClubsClient
from src.common_pydantic import BaseSchema
from src.events.config import settings
from src.events.schemas import OwnedClub


class ClubInfo(BaseSchema):
    id: str
    title: str
    slug: str


class ClubsClient:
    def __init__(self, api_url: str, api_key: str) -> None:
        self._api_url = api_url
        self._api_key = api_key
        self._http: httpx.AsyncClient | None = None

    @property
    def _api(self) -> GeneratedClubsClient:
        if self._http is None:
            self._http = httpx.AsyncClient()
        return GeneratedClubsClient(
            self._http,
            base_url=self._api_url,
            credentials={"Bearer": self._api_key, "HTTPBearer": self._api_key},
        )

    async def aclose(self) -> None:
        if self._http is not None:
            http, self._http = self._http, None
            await http.aclose()

    async def list_owned_clubs(self, innohassle_id: str) -> list[OwnedClub]:
        clubs = await self._api.get_clubs_owned_by_clubs_owned_by__innohassle_id__get(innohassle_id)
        return [OwnedClub(club_id=club.club_id, title=club.title) for club in clubs]

    async def list_all_clubs(self) -> list[OwnedClub]:
        clubs = await self._api.get_clubs_list_clubs__get()
        return [OwnedClub(club_id=str(club.id), title=club.title) for club in clubs]

    async def get_clubs(self, club_ids: set[str]) -> dict[str, ClubInfo]:
        """Fetch clubs by id; omitted ids were not found (404)."""
        if not club_ids:
            return {}

        async def fetch(club_id: str) -> tuple[str, ClubInfo | None]:
            try:
                club = await self._api.get_club_info_clubs_by_id__id__get(club_id)
            except ApiError as error:
                if error.status_code == 404:
                    return club_id, None
                raise
            return club_id, ClubInfo(id=str(club.id), title=club.title, slug=club.slug)

        pairs = await asyncio.gather(*(fetch(club_id) for club_id in club_ids))
        return {club_id: club for club_id, club in pairs if club is not None}


clubs_client = ClubsClient(
    api_url=settings.clubs.api_url,
    api_key=settings.clubs.api_key.get_secret_value(),
)
