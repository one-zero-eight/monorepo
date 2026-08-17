import datetime as dtm
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from src.schedule_assistant.modules.bookings.client import BmpBatchItemResult, BookingDTO, CancelAutoBookingsResult
from src.schedule_assistant.modules.bookings.review import (
    build_review_index,
    collect_booking_payloads,
    split_payloads_around_conflicts,
)
from src.schedule_assistant.modules.bookings.schemas import ConflictMode
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.schedule_config.repository import ScheduleConfigRepository
from src.schedule_assistant.modules.schedule_config.schemas import (
    ComponentSessionSeries,
    CourseConfig,
    CoursesConfig,
    RoomConfig,
    SectionConfig,
    SectionsConfig,
    SessionOccurrence,
    StudentsGroups,
    TermConfig,
    WeeklyPatternSlot,
)
from src.schedule_assistant.weekday import Weekday

MSK = dtm.timezone(dtm.timedelta(hours=3))


def _term() -> TermConfig:
    return TermConfig(
        name="Summer 2026",
        semester=TermConfig.DateRange(
            start_date=dtm.date(2026, 6, 1),
            end_date=dtm.date(2026, 8, 2),
        ),
    )


def _sections() -> SectionsConfig:
    return SectionsConfig(
        sections=[
            SectionConfig(
                code="core",
                name="Core",
                kind="core",
                programs=[SectionConfig.SectionProgram(code="BS", name="BS", groups=["G1"])],
            )
        ],
        students_groups=[StudentsGroups(code="G1", kind="core", estimated_size=10)],
    )


def _occurrence_courses(*, room: str | None = "107") -> CoursesConfig:
    return CoursesConfig(
        courses=[
            CourseConfig(
                name="Algorithms",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        student_groups=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                occurrences=[
                                    SessionOccurrence(
                                        date=dtm.date(2026, 6, 8),
                                        start_time=dtm.time(14, 20),
                                        end_time=dtm.time(15, 50),
                                        room=room,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _weekly_courses(*, room: str | None = "107") -> CoursesConfig:
    return CoursesConfig(
        courses=[
            CourseConfig(
                name="Algorithms",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        student_groups=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.MONDAY,
                                        start_time=dtm.time(14, 20),
                                        end_time=dtm.time(15, 50),
                                        room=room,
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def _seed(
    repo: ScheduleConfigRepository,
    *,
    courses: CoursesConfig,
    rooms: list[str] | None = None,
) -> None:
    repo.set_term(_term(), saved_by="test@test.com")
    repo.set_sections(_sections(), saved_by="test@test.com")
    repo.set_rooms(
        RoomConfig(rooms=[RoomConfig.Room(id=room_id, name=room_id) for room_id in (rooms or ["107"])]),
        saved_by="test@test.com",
    )
    repo.set_courses(courses, saved_by="test@test.com")


def _booking(
    *,
    title: str,
    start: str,
    end: str,
    room_id: str = "107",
    outlook_booking_id: str | None = None,
    categories: list[str] | None = None,
    recurrence: str | None = None,
) -> BookingDTO:
    return BookingDTO.model_validate(
        {
            "room_id": room_id,
            "title": title,
            "start": start,
            "end": end,
            "categories": categories,
            "recurrence": recurrence,
            "outlook_booking_id": outlook_booking_id,
        }
    )


@pytest.mark.asyncio
async def test_review_classifies_ready_booked_conflict_and_unbookable(
    authenticated_client: AsyncClient,
    bookings_repo: ScheduleConfigRepository,
    mock_booking_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    _seed(bookings_repo, courses=_occurrence_courses())
    mock_booking_client.get_all_bookings.return_value = []
    mock_booking_client.get_auto_bookings.return_value = []

    response = await authenticated_client.get("/bookings/review")
    assert response.status_code == 200
    payload = response.json()
    slot = payload["programs"][0]["courses"][0]["components"][0]["slots"][0]
    assert slot["review_kind"] == "ready"
    assert slot["bookable"] is True

    mock_booking_client.get_auto_bookings.return_value = [
        _booking(
            title="Schedule Assistant IU Auto: Algorithms (lec)",
            start="2026-06-08T14:20:00+03:00",
            end="2026-06-08T15:50:00+03:00",
            categories=["Auto", "core", "BS", "Algorithms"],
            outlook_booking_id="own-1",
        )
    ]
    booked = (await authenticated_client.get("/bookings/review")).json()
    assert booked["programs"][0]["courses"][0]["components"][0]["slots"][0]["review_kind"] == "booked"

    mock_booking_client.get_auto_bookings.return_value = []
    mock_booking_client.get_all_bookings.return_value = [
        _booking(
            title="Other event",
            start="2026-06-08T14:20:00+03:00",
            end="2026-06-08T15:50:00+03:00",
            categories=["external"],
        )
    ]
    conflicted = (await authenticated_client.get("/bookings/review")).json()
    conflict_slot = conflicted["programs"][0]["courses"][0]["components"][0]["slots"][0]
    assert conflict_slot["review_kind"] == "conflict"
    assert conflict_slot["conflicts"][0]["title"] == "Other event"

    _seed(bookings_repo, courses=_occurrence_courses(room="ONLINE"), rooms=["107"])
    mock_booking_client.get_all_bookings.return_value = []
    online = (await authenticated_client.get("/bookings/review")).json()
    online_slot = online["programs"][0]["courses"][0]["components"][0]["slots"][0]
    assert online_slot["bookable"] is False
    assert online_slot["disabled_reason"] == "online"


def test_unknown_room_is_not_bookable() -> None:
    slots = build_bookable_slots(_occurrence_courses(room="999"), _sections(), _term(), {"107"})
    assert slots[0].bookable is False
    assert slots[0].disabled_reason == "unknown room"


@pytest.mark.asyncio
async def test_review_lists_extra_auto_bookings(
    authenticated_client: AsyncClient,
    bookings_repo: ScheduleConfigRepository,
    mock_booking_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    _seed(bookings_repo, courses=_occurrence_courses())
    mock_booking_client.get_all_bookings.return_value = []
    mock_booking_client.get_auto_bookings.return_value = [
        _booking(
            title="Auto: Ghost course (lec)",
            start="2026-06-09T09:00:00+03:00",
            end="2026-06-09T10:30:00+03:00",
            categories=["Auto", "core", "BS", "Ghost course"],
            outlook_booking_id="extra-1",
        )
    ]

    response = await authenticated_client.get("/bookings/review")
    assert response.status_code == 200
    extras = response.json()["extra_auto_bookings"]
    assert len(extras) == 1
    assert extras[0]["extra_id"] == "id:extra-1"
    assert extras[0]["outlook_booking_id"] == "extra-1"


def test_split_weekly_slot_omits_conflict_dates() -> None:
    slots = build_bookable_slots(_weekly_courses(), _sections(), _term(), {"107"})
    weekly = next(slot for slot in slots if slot.payload.get("recurrence"))
    conflict_start = dtm.datetime(2026, 6, 15, 14, 20, tzinfo=MSK)
    conflict_end = dtm.datetime(2026, 6, 15, 15, 50, tzinfo=MSK)
    payloads = split_payloads_around_conflicts(
        weekly,
        [(conflict_start, conflict_end, [{"title": "Other", "room_id": "107"}])],
    )
    assert payloads
    for payload in payloads:
        recurrence = payload["recurrence"]
        start = dtm.date.fromisoformat(recurrence["start_date"])
        until = dtm.date.fromisoformat(recurrence["until_date"])
        assert not (start <= dtm.date(2026, 6, 15) <= until)


@pytest.mark.asyncio
async def test_batch_and_cancel_proxy_room_booking(
    authenticated_client: AsyncClient,
    bookings_repo: ScheduleConfigRepository,
    mock_booking_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    _seed(bookings_repo, courses=_occurrence_courses())
    mock_booking_client.get_all_bookings.return_value = []
    mock_booking_client.get_auto_bookings.return_value = []
    mock_booking_client.create_auto_bookings_batch.return_value = {
        "0": BmpBatchItemResult(status="ok", booking=None, error=None),
    }

    review = (await authenticated_client.get("/bookings/review")).json()
    slot_id = review["programs"][0]["courses"][0]["components"][0]["slots"][0]["slot_id"]
    response = await authenticated_client.post("/bookings/batch", json={"slot_ids": [slot_id], "conflict_modes": {}})
    assert response.status_code == 200
    body = response.json()
    assert body["submitted"] == 1
    assert body["results"][0]["status"] == "ok"
    mock_booking_client.create_auto_bookings_batch.assert_awaited_once()
    submitted = mock_booking_client.create_auto_bookings_batch.await_args.args[0]
    assert submitted[0]["title"] == "Algorithms (lec)"
    assert submitted[0]["room_id"] == "107"

    mock_booking_client.get_auto_bookings.return_value = [
        _booking(
            title="Auto: Ghost course (lec)",
            start="2026-06-09T09:00:00+03:00",
            end="2026-06-09T10:30:00+03:00",
            categories=["Auto", "core", "BS", "Ghost course"],
            outlook_booking_id="extra-1",
        )
    ]
    mock_booking_client.cancel_auto_bookings_batch.return_value = CancelAutoBookingsResult(
        cancelled=["extra-1"],
        failed={},
    )
    extra_review = (await authenticated_client.get("/bookings/review")).json()
    extra_id = extra_review["extra_auto_bookings"][0]["extra_id"]
    cancel_response = await authenticated_client.post("/bookings/cancel-extra", json={"extra_ids": [extra_id]})
    assert cancel_response.status_code == 200
    assert extra_id in cancel_response.json()["cancelled"]
    mock_booking_client.cancel_auto_bookings_batch.assert_awaited_once_with(["extra-1"])


def test_collect_payloads_skips_conflicts_by_default() -> None:
    slots = build_bookable_slots(_occurrence_courses(), _sections(), _term(), {"107"})
    existing = [
        _booking(
            title="Other event",
            start="2026-06-08T14:20:00+03:00",
            end="2026-06-08T15:50:00+03:00",
        )
    ]
    index = build_review_index(slots, auto_bookings=[], existing_bookings=existing)
    slot_id = slots[0].slot_id
    assert collect_booking_payloads(index, [slot_id], {}) == []
    booked = collect_booking_payloads(index, [slot_id], {slot_id: ConflictMode.BOOK})
    assert len(booked) == 1
    assert booked[0]["room_id"] == "107"
