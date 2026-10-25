import datetime
from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from src.timer.db.models import TimerPermission, TimerUserType

type Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200, pattern=r"^[^\x00]+$")
]


class CreateCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    time: AwareDatetime


class UpdateTimer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    start_time: AwareDatetime
    end_time: AwareDatetime
    checkpoints: list[CreateCheckpoint]


class CreateTimer(UpdateTimer):
    checkpoints: list[CreateCheckpoint] = Field(default_factory=list)


class ViewCheckpoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    title: str
    time: datetime.datetime


class ViewParticipant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    joined_at: datetime.datetime
    permissions: list[TimerPermission]
    user_type: TimerUserType


class ViewTimer(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    created_at: datetime.datetime
    updated_at: datetime.datetime
    checkpoints: list[ViewCheckpoint]
    participants: list[ViewParticipant]


class ViewInvitation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    uuid: UUID
    timer_id: int
