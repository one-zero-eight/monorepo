import datetime as dtm
from unittest.mock import Mock

import pytest
import respx
from beanie import PydanticObjectId
from fastapi.testclient import TestClient

from src.when2meet.modules.events import events_repo, routes
from src.when2meet.modules.events.schemas import BookedRoom

NOW = dtm.datetime(2027, 6, 15, 12, tzinfo=dtm.UTC)


@pytest.fixture
def meeting_clock(monkeypatch) -> Mock:
    clock = Mock(wraps=dtm)
    clock.datetime.now.return_value = NOW
    monkeypatch.setattr(routes, "dtm", clock)
    return clock


@pytest.mark.parametrize("booked", [False, True])
@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2027-06-15T10:00:00Z", "2027-06-15T11:00:00Z"),
        ("2027-06-15T10:00:00Z", "2027-06-15T13:00:00Z"),
        ("2027-06-15T12:00:00Z", "2027-06-15T13:00:00Z"),
        ("2027-06-15T15:00:00+03:00", "2027-06-15T16:00:00+03:00"),
    ],
)
def test_past_selected_time_rejects_entire_update_without_changing_booking(
    when2meet_client: TestClient, user_headers, meeting_clock, booked: bool, start: str, end: str
) -> None:
    created = when2meet_client.post(
        "/api/v0/meetings/",
        json={"name": "Future meeting", "slots": ["2027-06-15T18:00:00Z"]},
        headers=user_headers,
    ).json()
    path = f"/api/v0/meetings/{created['id']}"
    selected_time = {"start": "2027-06-15T15:00:00Z", "end": "2027-06-15T16:00:00Z"}
    assert when2meet_client.patch(path, json={"selected_time": selected_time}, headers=user_headers).status_code == 200

    portal = when2meet_client.portal
    assert portal is not None
    if booked:
        event = portal.call(events_repo.read, PydanticObjectId(created["id"]))
        assert event is not None
        event.booked_room = BookedRoom(room_id="3.2", outlook_booking_id="booking-1")
        portal.call(event.save)
    before = when2meet_client.get(path, headers=user_headers).json()

    with respx.mock as external_requests:
        response = when2meet_client.patch(
            path, json={"name": "Rejected rename", "selected_time": {"start": start, "end": end}}, headers=user_headers
        )
        assert len(external_requests.calls) == 0

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "selected_time_in_past",
        "message": "Meeting start time must be in the future",
    }
    after = when2meet_client.get(path, headers=user_headers).json()
    for field in ("name", "selected_time", "archive_after", "booked_room", "is_archived"):
        assert after[field] == before[field]
    stored = portal.call(events_repo.read, PydanticObjectId(created["id"]))
    assert stored is not None
    assert stored.room_booking_in_progress is False


@pytest.mark.parametrize("start", ["2027-06-15T12:00:01Z", "2027-06-15T15:00:01+03:00"])
def test_future_selected_time_is_accepted(
    when2meet_client: TestClient, user_headers, meeting_clock, start: str
) -> None:
    created = when2meet_client.post(
        "/api/v0/meetings/",
        json={"name": "Future meeting", "slots": ["2027-06-15T18:00:00Z"]},
        headers=user_headers,
    ).json()
    response = when2meet_client.patch(
        f"/api/v0/meetings/{created['id']}",
        json={"selected_time": {"start": start, "end": "2027-06-15T13:00:00Z"}},
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_archived"] is False
    assert response.json()["archive_after"] == "2027-06-15T13:00:00Z"


def test_started_meeting_can_be_read_renamed_and_keep_equivalent_selected_time(
    when2meet_client: TestClient, user_headers, meeting_clock
) -> None:
    meeting_clock.datetime.now.return_value = NOW - dtm.timedelta(hours=3)
    created = when2meet_client.post(
        "/api/v0/meetings/",
        json={"name": "Started meeting", "slots": ["2027-06-15T18:00:00Z"]},
        headers=user_headers,
    ).json()
    path = f"/api/v0/meetings/{created['id']}"
    selected_time = {"start": "2027-06-15T10:00:00Z", "end": "2027-06-15T13:00:00Z"}
    assert when2meet_client.patch(path, json={"selected_time": selected_time}, headers=user_headers).status_code == 200
    meeting_clock.datetime.now.return_value = NOW
    assert when2meet_client.get(path, headers=user_headers).json()["selected_time"] == selected_time

    response = when2meet_client.patch(path, json={"name": "Renamed"}, headers=user_headers)
    assert response.status_code == 200
    response = when2meet_client.patch(
        path,
        json={"selected_time": {"start": "2027-06-15T13:00:00+03:00", "end": "2027-06-15T16:00:00+03:00"}},
        headers=user_headers,
    )
    assert response.status_code == 200
    assert response.json()["is_archived"] is False

    response = when2meet_client.patch(path, json={"selected_time": None}, headers=user_headers)
    assert response.status_code == 200
    assert response.json()["selected_time"] is None
    assert response.json()["archive_after"] == created["archive_after"]


def test_microseconds_of_server_clock_are_not_rounded_down(
    when2meet_client: TestClient, user_headers, meeting_clock
) -> None:
    meeting_clock.datetime.now.return_value = NOW.replace(microsecond=500000)
    created = when2meet_client.post(
        "/api/v0/meetings/",
        json={"name": "Future meeting", "slots": ["2027-06-15T18:00:00Z"]},
        headers=user_headers,
    ).json()
    response = when2meet_client.patch(
        f"/api/v0/meetings/{created['id']}",
        json={"selected_time": {"start": "2027-06-15T12:00:00.900Z", "end": "2027-06-15T13:00:00Z"}},
        headers=user_headers,
    )
    assert response.status_code == 400
