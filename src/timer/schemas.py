import datetime as dtm
from typing import Annotated, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from src.timer.db.models import TimerPermission, TimerUserType

type Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class CreateCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    time: AwareDatetime


class CreateTimer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    start_time: AwareDatetime
    end_time: AwareDatetime
    checkpoints: list[CreateCheckpoint] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_time_range(self) -> Self:
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        if any(not self.start_time <= checkpoint.time <= self.end_time for checkpoint in self.checkpoints):
            raise ValueError("Checkpoint time must be within the timer interval")
        return self


class ViewCheckpoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    time: dtm.datetime


class ViewParticipant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    joined_at: dtm.datetime
    permissions: list[TimerPermission]
    user_type: TimerUserType


class ViewTimer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    start_time: dtm.datetime
    end_time: dtm.datetime
    created_at: dtm.datetime
    updated_at: dtm.datetime
    checkpoints: list[ViewCheckpoint]
    participants: list[ViewParticipant]
