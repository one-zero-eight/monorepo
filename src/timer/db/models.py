import datetime as dtm
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum, ForeignKey, Identity, Index, String, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class TimerPermission(StrEnum):
    UPDATE = "update"
    DELETE = "delete"
    INVITE = "invite"


class TimerUserType(StrEnum):
    CREATOR = "creator"
    PARTICIPANT = "participant"


class Base(DeclarativeBase):
    pass


class Timer(Base):
    __tablename__ = "timers"
    __table_args__ = (
        CheckConstraint("start_time < end_time", name="ck_timers_time_range"),
        CheckConstraint("jsonb_typeof(checkpoints) = 'array'", name="ck_timers_checkpoints_array"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    start_time: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dtm.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    participants: Mapped[list[TimerParticipant]] = relationship(
        back_populates="timer", cascade="all, delete-orphan", passive_deletes=True
    )
    checkpoints: Mapped[list[dict[str, str]]] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    "Checkpoints with title/time. Assign a new list when editing to persist JSON changes."


class TimerParticipant(Base):
    __tablename__ = "timer_participants"
    __table_args__ = (
        Index("uq_timer_participants_creator", "timer_id", unique=True, postgresql_where=text("user_type = 'creator'")),
    )

    timer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("timers.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    "InNoHassle Accounts user ID"
    joined_at: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    permissions: Mapped[list[TimerPermission]] = mapped_column(
        MutableList.as_mutable(
            ARRAY(
                Enum(
                    TimerPermission,
                    name="timer_permission",
                    values_callable=lambda enum: [item.value for item in enum],
                    validate_strings=True,
                )
            )
        ),
        default=list,
        server_default=text("'{}'::timer_permission[]"),
    )
    user_type: Mapped[TimerUserType] = mapped_column(
        Enum(
            TimerUserType,
            name="timer_user_type",
            values_callable=lambda enum: [item.value for item in enum],
            validate_strings=True,
        )
    )

    timer: Mapped[Timer] = relationship(back_populates="participants")


class Invitation(Base):
    __tablename__ = "invitations"

    uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    timer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("timers.id", ondelete="CASCADE"), index=True)
