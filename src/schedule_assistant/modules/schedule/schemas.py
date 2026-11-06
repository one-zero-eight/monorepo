from pydantic import Field

from src.schedule_assistant.schema_base import ScheduleAssistantSchema


class VirtualEventGroup(ScheduleAssistantSchema):
    id: None = None
    alias: str
    name: str
    description: str
    group_code: str | None = None
    instructor_id: str | None = None


class ListVirtualEventGroupsResponse(ScheduleAssistantSchema):
    event_groups: list[VirtualEventGroup] = Field(default_factory=list)


class PredefinedAliasesResponse(ScheduleAssistantSchema):
    event_groups: list[str] = Field(default_factory=list)


class UserStudentGroup(ScheduleAssistantSchema):
    code: str
    "Student group code (group/program/selector id)"
    name: str | None = None
    "Optional display name"


class UserStudentGroupsResponse(ScheduleAssistantSchema):
    groups: list[UserStudentGroup] = Field(default_factory=list)


class BatchAliasesIcsRequest(ScheduleAssistantSchema):
    aliases: list[str] = Field(default_factory=list)
