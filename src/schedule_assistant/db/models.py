import datetime as dtm
from typing import Any

from sqlalchemy import JSON, Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.schedule_assistant.db.base import Base


class TermRow(Base):
    __tablename__ = "term"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String, nullable=False)
    semester_start: Mapped[dtm.date] = mapped_column(Date, nullable=False)
    semester_end: Mapped[dtm.date] = mapped_column(Date, nullable=False)
    days: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    starting_day: Mapped[str] = mapped_column(String, nullable=False)
    time_slots: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    sections: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    instructor_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class StudentGroupRow(Base):
    __tablename__ = "student_groups"

    code: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    students: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class CourseRow(Base):
    __tablename__ = "courses"

    name: Mapped[str] = mapped_column(String, primary_key=True)
    short_name: Mapped[str | None] = mapped_column(String, nullable=True)
    name_ru: Mapped[str | None] = mapped_column(String, nullable=True)
    short_name_ru: Mapped[str | None] = mapped_column(String, nullable=True)
    course_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    components: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)


class InstructorRow(Base):
    __tablename__ = "instructors"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name_en: Mapped[str | None] = mapped_column(String, nullable=True)
    name_ru: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    alias: Mapped[str | None] = mapped_column(String, nullable=True)
    position: Mapped[str | None] = mapped_column(String, nullable=True)
    slot_preferences: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


class RoomRow(Base):
    __tablename__ = "rooms"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class ConfigMetaRow(Base):
    __tablename__ = "config_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ConfigHistoryEventRow(Base):
    __tablename__ = "config_history_events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    resources: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    saved_at: Mapped[str] = mapped_column(String, nullable=False)
    saved_by: Mapped[str] = mapped_column(String, nullable=False)
    patch: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
