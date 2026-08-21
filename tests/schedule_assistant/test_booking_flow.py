import asyncio
import datetime as dtm
from unittest.mock import AsyncMock

import httpx
import pytest
from httpx import AsyncClient

from src.schedule_assistant.modules.bookings.client import BmpStreamEvent, BmpStreamEventKind, BookingDTO
from src.schedule_assistant.modules.bookings.review import (
    build_review_index,
    collect_booking_payloads,
    slot_label,
    split_payloads_around_conflicts,
)
from src.schedule_assistant.modules.bookings.schemas import BookingItemResultStatus, ConflictMode
from src.schedule_assistant.modules.issues.booking_slots import build_bookable_slots
from src.schedule_assistant.modules.issues.booking_window import (
    BOOKING_FETCH_MAX_DAYS,
    resolve_booking_fetch_window,
)
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


def _freeze_booking_now(monkeypatch: pytest.MonkeyPatch, instant: dtm.datetime) -> None:
    def fake_resolve(
        start_date: dtm.date,
        end_date: dtm.date,
        *,
        now: dtm.datetime | None = None,
    ) -> tuple[dtm.datetime, dtm.datetime] | None:
        return resolve_booking_fetch_window(start_date, end_date, now=instant)

    monkeypatch.setattr(
        "src.schedule_assistant.modules.bookings.service.resolve_booking_fetch_window",
        fake_resolve,
    )


@pytest.fixture(autouse=True)
def freeze_booking_window_now(monkeypatch: pytest.MonkeyPatch) -> None:
    _freeze_booking_now(monkeypatch, dtm.datetime(2026, 6, 1, 12, 0, tzinfo=MSK))


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
                        audience=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                dates_pattern=[
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
                        audience=["G1"],
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


@pytest.mark.asyncio
async def test_review_caps_booking_fetch_to_ews_limit(
    authenticated_client: AsyncClient,
    bookings_repo: ScheduleConfigRepository,
    mock_booking_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    _freeze_booking_now(monkeypatch, dtm.datetime(2026, 8, 18, 7, 48, tzinfo=MSK))

    _seed(bookings_repo, courses=_occurrence_courses())
    bookings_repo.set_term(
        TermConfig(
            name="Fall 2026",
            semester=TermConfig.DateRange(
                start_date=dtm.date(2026, 8, 24),
                end_date=dtm.date(2026, 12, 24),
            ),
        ),
        saved_by="test@test.com",
    )
    mock_booking_client.get_all_bookings.return_value = []
    mock_booking_client.get_auto_bookings.return_value = []

    response = await authenticated_client.get("/bookings/review")
    assert response.status_code == 200
    mock_booking_client.get_all_bookings.assert_awaited_once()
    start, end = mock_booking_client.get_all_bookings.await_args.args
    assert start == dtm.datetime(2026, 8, 24, 0, 0, tzinfo=MSK)
    assert end - start <= dtm.timedelta(days=BOOKING_FETCH_MAX_DAYS)
    assert mock_booking_client.get_auto_bookings.await_args.args == (start, end)


def test_unknown_room_is_not_bookable() -> None:
    slots = build_bookable_slots(_occurrence_courses(room="999"), _sections(), _term(), {"107"})
    assert slots[0].bookable is False
    assert slots[0].disabled_reason == "unknown room"


def _split_lec_courses() -> CoursesConfig:
    return CoursesConfig(
        courses=[
            CourseConfig(
                name="Security",
                section_code="core",
                components=[
                    CourseConfig.Component(
                        tag="lec",
                        audience=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.TUESDAY,
                                        start_time=dtm.time(10, 40),
                                        end_time=dtm.time(12, 10),
                                        room="107",
                                    ),
                                ],
                            ),
                        ],
                    ),
                    CourseConfig.Component(
                        tag="lec",
                        audience=["G1"],
                        sessions=[
                            ComponentSessionSeries(
                                audience=["G1"],
                                weekly_pattern=[
                                    WeeklyPatternSlot(
                                        weekday=Weekday.WEDNESDAY,
                                        start_time=dtm.time(12, 40),
                                        end_time=dtm.time(14, 10),
                                        room="106",
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


def test_split_lec_components_keep_distinct_slot_ids() -> None:
    slots = build_bookable_slots(_split_lec_courses(), _sections(), _term(), {"107", "106"})
    slot_ids = [slot.slot_id for slot in slots]
    assert len(slot_ids) == 2
    assert len(set(slot_ids)) == 2

    index = build_review_index(slots, auto_bookings=[], existing_bookings=[])
    review_slots = [
        slot
        for program in index.tree.programs
        for course in program.courses
        for component in course.components
        for slot in component.slots
    ]
    assert {slot.slot_id for slot in review_slots} == set(slot_ids)
    assert {slot.date.lower() for slot in review_slots} == {"tuesday", "wednesday"}


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


async def _wait_task(client: AsyncClient, task_id: str) -> dict:
    body: dict = {}
    for _ in range(100):
        poll = await client.get(f"/bookings/tasks/{task_id}")
        assert poll.status_code == 200
        body = poll.json()
        if body["status"] in {"done", "error"}:
            return body
        await asyncio.sleep(0.05)
    raise AssertionError(f"task {task_id} did not finish: {body}")


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

    submitted: list = []

    async def fake_stream(payloads):
        submitted.append(payloads)
        title = str(payloads[0].get("title") or "")
        yield BmpStreamEvent(event=BmpStreamEventKind.STARTED, total=1)
        yield BmpStreamEvent(event=BmpStreamEventKind.SENT, indexes=["0"])
        yield BmpStreamEvent(
            event=BmpStreamEventKind.ITEM,
            index="0",
            status=BookingItemResultStatus.OK,
            title=title,
        )
        yield BmpStreamEvent(event=BmpStreamEventKind.DONE)

    mock_booking_client.stream_auto_bookings_batch = fake_stream

    review = (await authenticated_client.get("/bookings/review")).json()
    slot_id = review["programs"][0]["courses"][0]["components"][0]["slots"][0]["slot_id"]
    response = await authenticated_client.post("/bookings/batch", json={"slot_ids": [slot_id], "conflict_modes": {}})
    assert response.status_code == 200
    started = response.json()
    assert started["kind"] == "book"
    body = await _wait_task(authenticated_client, started["task_id"])
    assert body["status"] == "done"
    assert body["sent"] == 1
    assert body["done"] == 1
    assert body["items"][0]["status"] == "ok"
    assert body["items"][0]["title"] == "Algorithms (lec)"
    assert len(submitted) == 1
    assert submitted[0][0]["title"] == "Algorithms (lec)"
    assert submitted[0][0]["room_id"] == "107"

    mock_booking_client.get_auto_bookings.return_value = [
        _booking(
            title="Auto: Ghost course (lec)",
            start="2026-06-09T09:00:00+03:00",
            end="2026-06-09T10:30:00+03:00",
            categories=["Auto", "core", "BS", "Ghost course"],
            outlook_booking_id="extra-1",
        )
    ]
    extra_review = (await authenticated_client.get("/bookings/review")).json()
    extra_id = extra_review["extra_auto_bookings"][0]["extra_id"]
    cancel_response = await authenticated_client.post("/bookings/cancel-extra", json={"extra_ids": [extra_id]})
    assert cancel_response.status_code == 200
    cancel_body = await _wait_task(authenticated_client, cancel_response.json()["task_id"])
    assert cancel_body["status"] == "done"
    assert extra_id in cancel_body["cancel"]["cancelled"]
    mock_booking_client.cancel_auto_booking.assert_awaited_once_with("extra-1")


@pytest.mark.asyncio
async def test_batch_marks_ok_when_stream_drops_after_outlook_create(
    authenticated_client: AsyncClient,
    bookings_repo: ScheduleConfigRepository,
    mock_booking_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    _seed(bookings_repo, courses=_occurrence_courses())
    mock_booking_client.get_all_bookings.return_value = []
    captured: list[dict] = []

    async def fake_stream(payloads):
        captured.extend(payloads)
        raise httpx.RemoteProtocolError(
            "peer closed connection without sending complete message body (incomplete chunked read)"
        )
        yield

    async def fake_auto_bookings(*_args, **_kwargs):
        if not captured:
            return []
        payload = captured[0]
        return [
            _booking(
                title=f"Auto: {payload['title']}",
                start=str(payload["start"]),
                end=str(payload["end"]),
                room_id=str(payload["room_id"]),
                categories=list(payload.get("categories") or []),
            )
        ]

    mock_booking_client.stream_auto_bookings_batch = fake_stream
    mock_booking_client.get_auto_bookings.side_effect = fake_auto_bookings

    review = (await authenticated_client.get("/bookings/review")).json()
    slot_id = review["programs"][0]["courses"][0]["components"][0]["slots"][0]["slot_id"]
    response = await authenticated_client.post("/bookings/batch", json={"slot_ids": [slot_id], "conflict_modes": {}})
    assert response.status_code == 200
    body = await _wait_task(authenticated_client, response.json()["task_id"])
    assert body["status"] == "done"
    assert body["error"] is None
    assert body["items"][0]["status"] == "ok"


@pytest.mark.asyncio
async def test_batch_does_not_leave_pending_when_stream_drops_unmatched(
    authenticated_client: AsyncClient,
    bookings_repo: ScheduleConfigRepository,
    mock_booking_client: AsyncMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("src.schedule_assistant.dependencies.settings.moderator_emails", ["test@test.com"])
    _seed(bookings_repo, courses=_occurrence_courses())
    mock_booking_client.get_all_bookings.return_value = []
    mock_booking_client.get_auto_bookings.return_value = []

    async def fake_stream(_payloads):
        raise httpx.RemoteProtocolError("incomplete chunked read")
        yield

    mock_booking_client.stream_auto_bookings_batch = fake_stream

    review = (await authenticated_client.get("/bookings/review")).json()
    slot_id = review["programs"][0]["courses"][0]["components"][0]["slots"][0]["slot_id"]
    response = await authenticated_client.post("/bookings/batch", json={"slot_ids": [slot_id], "conflict_modes": {}})
    assert response.status_code == 200
    body = await _wait_task(authenticated_client, response.json()["task_id"])
    assert body["status"] == "done"
    assert body["items"][0]["status"] == "error"
    assert "incomplete chunked read" in (body["items"][0]["error"] or "")


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


def test_weekly_slot_label_is_russian() -> None:
    assert (
        slot_label(
            {
                "start": "2026-08-24T09:00:00+03:00",
                "end": "2026-08-24T10:30:00+03:00",
                "recurrence": {"weekday": "monday"},
            },
            room="108",
            disabled_reason=None,
        )
        == "Каждый понедельник 09:00–10:30 (108)"
    )


def test_occurrence_slot_label_is_russian() -> None:
    assert (
        slot_label(
            {
                "start": "2026-06-08T14:20:00+03:00",
                "end": "2026-06-08T15:50:00+03:00",
            },
            room="107",
            disabled_reason=None,
        )
        == "Понедельник 08.06.2026 14:20–15:50 (107)"
    )


def test_review_tree_uses_russian_weekly_labels() -> None:
    slots = build_bookable_slots(_weekly_courses(), _sections(), _term(), {"107"})
    index = build_review_index(slots, auto_bookings=[], existing_bookings=[])
    labels = [
        slot.label
        for program in index.tree.programs
        for course in program.courses
        for component in course.components
        for slot in component.slots
    ]
    assert labels
    assert all("Каждый понедельник" in label for label in labels)
    assert all("Weekly" not in label and "MONDAY" not in label for label in labels)
