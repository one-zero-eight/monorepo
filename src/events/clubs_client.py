"""InNoHassle Clubs service REST client (authorized with a service API key)."""

import httpx

from src.events.config import settings
from src.events.schemas import OwnedClub


class ClubsClient:
    def __init__(self, api_url: str, api_key: str) -> None:
        self._api_url = api_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    async def list_owned_clubs(self, innohassle_id: str) -> list[OwnedClub]:
        async with httpx.AsyncClient(headers=self._headers) as client:
            response = await client.get(f"{self._api_url}/clubs/owned-by/{innohassle_id}")
            response.raise_for_status()
            return [OwnedClub.model_validate(item) for item in response.json()]


clubs_client = ClubsClient(
    api_url=settings.clubs.api_url,
    api_key=settings.clubs.api_key.get_secret_value(),
)
