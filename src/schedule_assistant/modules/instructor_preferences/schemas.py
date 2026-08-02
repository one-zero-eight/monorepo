import datetime as dtm

from src.schedule_assistant.modules.schedule_config.schemas import (
    InstructorSlotPreferenceEntry,
    TermConfig,
)
from src.schedule_assistant.schema_base import ScheduleAssistantSchema


class InstructorPreferenceForm(ScheduleAssistantSchema):
    instructor_id: str
    instructor_name: str
    email: str | None = None
    term: TermConfig
    slot_preferences: list[InstructorSlotPreferenceEntry]


class InstructorPreferenceUpdate(ScheduleAssistantSchema):
    slot_preferences: list[InstructorSlotPreferenceEntry]


class PreferenceShareLinkResponse(ScheduleAssistantSchema):
    token: str
    expires_at: dtm.datetime
