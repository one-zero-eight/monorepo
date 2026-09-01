from typing import NoReturn
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from src.schedule.config import settings

TIMEOUT = 60


class AssistantEventGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")

    alias: str
    name: str
    description: str | None = None
    tags: list[dict] = Field(default_factory=list)


class ScheduleAssistantClient:
    @staticmethod
    def _raise_upstream_error(error: httpx.HTTPError) -> NoReturn:
        status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
        detail = f"Schedule Assistant request failed{f' with status {status}' if status else ''}"
        raise HTTPException(status_code=502, detail=detail) from error

    def _client(self) -> httpx.AsyncClient:
        integration = settings.schedule_assistant
        if integration is None:
            raise RuntimeError("Schedule Assistant integration is not configured")
        return httpx.AsyncClient(
            base_url=integration.api_url.rstrip("/") + "/",
            headers={"Authorization": f"Bearer {integration.api_key.get_secret_value()}"},
            timeout=TIMEOUT,
        )

    async def get_event_groups(self) -> list[AssistantEventGroup]:
        try:
            async with self._client() as client:
                response = await client.get("integration/event-groups")
                response.raise_for_status()
        except httpx.HTTPError as error:
            self._raise_upstream_error(error)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload["event_groups"]
        return TypeAdapter(list[AssistantEventGroup]).validate_python(payload)

    async def get_user_predefined(self, email: str) -> list[str]:
        try:
            async with self._client() as client:
                response = await client.get(f"integration/users/{quote(email, safe='')}/predefined")
                response.raise_for_status()
        except httpx.HTTPError as error:
            self._raise_upstream_error(error)
        payload = response.json()
        if isinstance(payload, dict):
            payload = payload["event_groups"]
        return TypeAdapter(list[str]).validate_python(payload)

    async def get_event_group_ics(self, alias: str) -> bytes:
        try:
            async with self._client() as client:
                response = await client.get(f"integration/event-groups/{quote(alias, safe='')}/schedule.ics")
                response.raise_for_status()
                return response.content
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise HTTPException(status_code=404, detail="Event group not found") from error
            self._raise_upstream_error(error)
        except httpx.HTTPError as error:
            self._raise_upstream_error(error)

    async def get_event_groups_ics(self, aliases: list[str]) -> bytes:
        try:
            async with self._client() as client:
                response = await client.post(
                    "integration/event-groups/schedule.ics",
                    json={"aliases": aliases},
                )
                response.raise_for_status()
                return response.content
        except httpx.HTTPError as error:
            self._raise_upstream_error(error)


schedule_assistant_client = ScheduleAssistantClient()
