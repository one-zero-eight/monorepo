from typing import NoReturn

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field

from src.clients.schedule_assistant import ScheduleAssistantClient as GeneratedScheduleAssistantClient
from src.clients.schedule_assistant.exceptions import ApiError, ClientError
from src.clients.schedule_assistant.models import BatchAliasesIcsRequest
from src.schedule.config import settings

TIMEOUT = 60


class AssistantEventGroup(BaseModel):
    model_config = ConfigDict(extra="ignore")

    alias: str
    name: str
    description: str | None = None
    tags: list[dict] = Field(default_factory=list)


class ScheduleAssistantClient:
    def __init__(self) -> None:
        self._http: httpx.AsyncClient | None = None

    @staticmethod
    def _raise_upstream_error(error: ClientError) -> NoReturn:
        status = error.status_code if isinstance(error, ApiError) else None
        detail = f"Schedule Assistant request failed{f' with status {status}' if status else ''}"
        raise HTTPException(status_code=502, detail=detail) from error

    def _client(self) -> GeneratedScheduleAssistantClient:
        integration = settings.schedule_assistant
        if integration is None:
            raise RuntimeError("Schedule Assistant integration is not configured")
        if self._http is None:
            self._http = httpx.AsyncClient()
        return GeneratedScheduleAssistantClient(
            self._http,
            base_url=integration.api_url,
            credentials={"Bearer": integration.api_key.get_secret_value()},
            timeout=TIMEOUT,
        )

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def get_event_groups(self) -> list[AssistantEventGroup]:
        try:
            response = await self._client().schedule_integration_list_event_groups()
        except ClientError as error:
            self._raise_upstream_error(error)
        return [AssistantEventGroup.model_validate(group.model_dump()) for group in response.event_groups]

    async def get_user_predefined(self, email: str) -> list[str]:
        try:
            response = await self._client().schedule_integration_get_predefined_aliases(email)
        except ClientError as error:
            self._raise_upstream_error(error)
        return response.event_groups

    async def get_event_group_ics(self, alias: str) -> bytes:
        try:
            response = await self._client().schedule_integration_get_event_group_ics(alias)
            return response.encode("utf-8")
        except ApiError as error:
            if error.status_code == 404:
                raise HTTPException(status_code=404, detail="Event group not found") from error
            self._raise_upstream_error(error)
        except ClientError as error:
            self._raise_upstream_error(error)

    async def get_event_groups_ics(self, aliases: list[str]) -> bytes:
        try:
            response = await self._client().schedule_integration_get_event_groups_ics(
                BatchAliasesIcsRequest(aliases=aliases)
            )
            return response.encode("utf-8")
        except ClientError as error:
            self._raise_upstream_error(error)


schedule_assistant_client = ScheduleAssistantClient()
