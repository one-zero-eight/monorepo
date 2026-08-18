import datetime as dtm
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Integer, LargeBinary, String
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
    instructor_positions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    course_instructor_roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    course_component_tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    room_attributes: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)


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
    section_code: Mapped[str] = mapped_column(String, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String, nullable=True)
    name_ru: Mapped[str | None] = mapped_column(String, nullable=True)
    short_name_ru: Mapped[str | None] = mapped_column(String, nullable=True)
    instructors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
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


class PreferenceInviteLinkRow(Base):
    __tablename__ = "preference_invite_links"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    instructor_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    expires_at: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)


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


class DistributionUploadRow(Base):
    __tablename__ = "distribution_uploads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    section_code: Mapped[str] = mapped_column(String, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[str] = mapped_column(String, nullable=False)
    file_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sheet_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email_column: Mapped[str | None] = mapped_column(String, nullable=True)
    membership_columns: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    mapping: Mapped[dict[str, str | None]] = mapped_column(JSON, nullable=False, default=dict)
    stats: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    updated_groups: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    skipped_labels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class BookingTaskRow(Base):
    __tablename__ = "booking_tasks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    current: Mapped[str | None] = mapped_column(String, nullable=True)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[dtm.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
