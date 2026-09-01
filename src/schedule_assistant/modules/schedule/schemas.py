from pydantic import Field

from src.schedule_assistant.schema_base import ScheduleAssistantSchema


class VirtualEventGroup(ScheduleAssistantSchema):
    id: None = None
    alias: str
    name: str
    description: str
    kind: str
    group_code: str


class ListVirtualEventGroupsResponse(ScheduleAssistantSchema):
    event_groups: list[VirtualEventGroup] = Field(default_factory=list)


class PredefinedAliasesResponse(ScheduleAssistantSchema):
    event_groups: list[str] = Field(default_factory=list)


class BatchAliasesIcsRequest(ScheduleAssistantSchema):
    aliases: list[str] = Field(default_factory=list)
