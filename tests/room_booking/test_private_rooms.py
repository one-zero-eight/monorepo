import datetime as dtm
from unittest.mock import MagicMock

import exchangelib
import pytest
from exchangelib.services.get_user_availability import FreeBusyView
from joserfc import jwt

from src.inh_accounts_sdk import InnopolisInfo
from src.room_booking.config_schema import AccessToRoom, Room
from src.room_booking.modules.bookings.caching import CacheForBookings
from src.room_booking.modules.bookings.exchange_repository import exchange_booking_repository
from src.room_booking.modules.bookings.recently import RecentBookings
from src.room_booking.modules.bookings.tz_utils import msk_timezone
from src.room_booking.modules.rooms.repository import RoomsRepository, room_repository
from src.room_booking.modules.rules.service import can_book
from tests.room_booking.datetime_helpers import dt_params

ALLOWED_EMAIL = "test-user-1@innopolis.university"


@pytest.fixture
def private_room(monkeypatch: pytest.MonkeyPatch) -> Room:
    room = Room(
        id="private-test",
        title="Private room",
        short_name="Private",
        resource_email="private-test@innopolis.ru",
        access_level="yellow",
        private=True,
    )
    repository = RoomsRepository(
        [*room_repository.rooms, room],
        {**room_repository.access_lists, room.id: [AccessToRoom(email=ALLOWED_EMAIL)]},
    )
    for attribute in ("rooms", "room_by_id", "room_by_email", "access_lists", "email_x_access_list"):
        monkeypatch.setattr(room_repository, attribute, getattr(repository, attribute))
    return room


@pytest.fixture
def slot() -> tuple[dtm.datetime, dtm.datetime]:
    start = (dtm.datetime.now(msk_timezone) + dtm.timedelta(days=1)).replace(hour=20, minute=0, second=0, microsecond=0)
    return start, start + dtm.timedelta(hours=1)


@pytest.fixture
def exchange_account(monkeypatch: pytest.MonkeyPatch, private_room: Room, slot):
    start, end = slot
    item = exchangelib.CalendarItem(
        account=exchange_booking_repository.account,
        id="private-booking",
        subject="Private meeting",
        start=exchangelib.EWSDateTime.from_datetime(start),
        end=exchangelib.EWSDateTime.from_datetime(end),
        required_attendees=[
            exchangelib.Attendee(mailbox=exchangelib.Mailbox(email_address=email), response_type="Accept")
            for email in (private_room.resource_email, ALLOWED_EMAIL, "admin@innopolis.university")
        ],
    )
    account = MagicMock()
    account.root.get.return_value = item
    account.calendar.view.return_value.only.return_value = [item]
    account.protocol.get_free_busy_info.side_effect = lambda accounts, **_: [
        FreeBusyView(view_type="Detailed", calendar_events=[]) for _ in accounts
    ]
    monkeypatch.setattr(exchange_booking_repository, "account", account)
    monkeypatch.setattr(exchange_booking_repository, "_cache_from_account_calendar", CacheForBookings(60))
    monkeypatch.setattr(exchange_booking_repository, "_cache_from_busy_info", CacheForBookings(60))
    monkeypatch.setattr(exchange_booking_repository, "_recently", RecentBookings(300))
    return account


def test_rooms_are_public_by_default():
    room = Room(id="public", title="Public", short_name="Public", resource_email="public@innopolis.ru")
    assert room.private is False


@pytest.mark.parametrize(
    "headers_fixture,visible", [("user_headers", True), ("superadmin_headers", False), ("api_key_headers", True)]
)
def test_private_room_visibility(room_booking_client, request, private_room, headers_fixture, visible):
    response = room_booking_client.get("/rooms/", headers=request.getfixturevalue(headers_fixture))
    assert response.status_code == 200
    rooms = {room["id"]: room for room in response.json()}
    assert (private_room.id in rooms) is visible
    assert rooms["3.1"]["private"] is False
    if visible:
        assert rooms[private_room.id]["private"] is True


def test_private_room_in_my_access_list(room_booking_client, user_headers, private_room):
    response = room_booking_client.get("/rooms/my-access-list", headers=user_headers)
    assert response.status_code == 200
    assert private_room.id in {room["id"] for room in response.json()}


@pytest.mark.parametrize("path", ["", "/can-book", "/bookings"])
def test_private_room_direct_access_denied(room_booking_client, superadmin_headers, private_room, slot, path):
    start, end = slot
    response = room_booking_client.get(
        f"/room/{private_room.id}{path}", headers=superadmin_headers, params=dt_params(start=start, end=end)
    )
    assert response.status_code == 403


@pytest.mark.parametrize("path", ["", "/can-book", "/bookings"])
def test_private_room_direct_access_allowed(
    room_booking_client, user_headers, private_room, slot, exchange_account, path
):
    start, end = slot
    response = room_booking_client.get(
        f"/room/{private_room.id}{path}", headers=user_headers, params=dt_params(start=start, end=end)
    )
    assert response.status_code == 200
    if path == "/can-book":
        assert response.json()["can_book"] is True
    elif path == "/bookings":
        assert response.json()[0]["title"] == "Private meeting"
    else:
        assert response.json()["private"] is True


@pytest.mark.parametrize(
    "params",
    [{"room_id": "private-test"}, {"room_ids": ["private-test"]}, {"room_id": "3.1", "room_ids": ["private-test"]}],
)
def test_private_room_bulk_explicit_access_denied(room_booking_client, superadmin_headers, private_room, params):
    response = room_booking_client.get("/bookings/", headers=superadmin_headers, params=params)
    assert response.status_code == 403


@pytest.mark.parametrize(
    "headers_fixture,visible", [("user_headers", True), ("superadmin_headers", False), ("api_key_headers", True)]
)
def test_private_room_bulk_schedule_filtered(
    room_booking_client, request, private_room, exchange_account, headers_fixture, visible
):
    response = room_booking_client.get("/bookings/", headers=request.getfixturevalue(headers_fixture))
    assert response.status_code == 200
    assert (private_room.id in {booking["room_id"] for booking in response.json()}) is visible


@pytest.mark.parametrize("headers_fixture,visible", [("user_headers", True), ("superadmin_headers", False)])
def test_private_my_bookings_filtered_even_for_invited_user(
    room_booking_client, request, private_room, exchange_account, headers_fixture, visible
):
    response = room_booking_client.get("/bookings/my", headers=request.getfixturevalue(headers_fixture))
    assert response.status_code == 200
    assert (private_room.id in {booking["room_id"] for booking in response.json()}) is visible


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_private_booking_direct_id_denied_even_for_participant(
    room_booking_client, superadmin_headers, exchange_account, method
):
    kwargs = {"json": {"title": "Changed", "start": None, "end": None}} if method == "patch" else {}
    response = getattr(room_booking_client, method)("/bookings/private-booking", headers=superadmin_headers, **kwargs)
    assert response.status_code == 403


def test_private_booking_direct_id_allowed(room_booking_client, user_headers, exchange_account):
    response = room_booking_client.get("/bookings/private-booking", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["title"] == "Private meeting"


@pytest.mark.parametrize("method", ["get", "delete"])
def test_private_booking_entry_id_denied(room_booking_client, superadmin_headers, private_room, method):
    response = getattr(room_booking_client, method)(
        "/bookings/by-entry-id/entry", params={"room_id": private_room.id}, headers=superadmin_headers
    )
    assert response.status_code == 403


def test_private_booking_attendee_details_denied(room_booking_client, superadmin_headers, exchange_account):
    response = room_booking_client.get(
        "/bookings/private-booking/get-attendee-details",
        params={"user_email": ALLOWED_EMAIL},
        headers=superadmin_headers,
    )
    assert response.status_code == 403


def test_private_booking_attendee_details_allowed(room_booking_client, user_headers, exchange_account):
    response = room_booking_client.get(
        "/bookings/private-booking/get-attendee-details", params={"user_email": ALLOWED_EMAIL}, headers=user_headers
    )
    assert response.status_code == 200
    assert response.json()["email"] == ALLOWED_EMAIL


@pytest.mark.parametrize("through_participants", [False, True])
def test_private_booking_create_denied(
    room_booking_client, superadmin_headers, private_room, slot, through_participants
):
    start, end = slot
    response = room_booking_client.post(
        "/bookings/",
        headers=superadmin_headers,
        json={
            "room_id": "3.1" if through_participants else private_room.id,
            "title": "Meeting",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "participant_emails": [private_room.resource_email] if through_participants else [],
        },
    )
    assert response.status_code == 403


def test_private_room_without_access_list_is_hidden(room_booking_client, user_headers, private_room, monkeypatch):
    monkeypatch.setattr(room_repository, "email_x_access_list", {})
    response = room_booking_client.get(f"/room/{private_room.id}", headers=user_headers)
    assert response.status_code == 403


@pytest.mark.parametrize("is_staff", [False, True])
def test_private_booking_rules_require_access_list(private_room, slot, is_staff):
    start, end = slot
    user = InnopolisInfo(
        email="outsider@innopolis.university", is_student=not is_staff, is_staff=is_staff, updated_at=start
    )
    allowed, reason = can_book(user=user, room=private_room, start=start, end=end)
    assert allowed is False
    assert "private room" in reason


@pytest.mark.parametrize("access_level", ["yellow", "red", "special", None])
@pytest.mark.parametrize("is_staff", [False, True])
def test_private_booking_rules_allow_listed_user(private_room, slot, access_level, is_staff):
    start, end = slot
    room = private_room.model_copy(update={"access_level": access_level})
    user = InnopolisInfo(email=ALLOWED_EMAIL, is_student=not is_staff, is_staff=is_staff, updated_at=start)
    allowed, reason = can_book(user=user, room=room, start=start, end=end)
    assert allowed is True
    assert not reason


@pytest.fixture
def room_tv_headers(jwt_keypair):
    private_key, _ = jwt_keypair

    def headers(room_id: str):
        now = int(dtm.datetime.now(dtm.UTC).timestamp())
        token = jwt.encode(
            {"alg": "RS256", "kid": "public"},
            {"room_id": room_id, "aud": "room-booking", "iat": now, "exp": now + 3600},
            private_key,
        )
        return {"Authorization": f"Bearer {token}"}

    return headers


def test_private_tv_token_rejected(room_booking_client, room_tv_headers, private_room, slot):
    start, end = slot
    response = room_booking_client.get(
        f"/room/{private_room.id}/bookings",
        headers=room_tv_headers(private_room.id),
        params=dt_params(start=start, end=end),
    )
    assert response.status_code == 401


@pytest.mark.parametrize("target_room,status", [("3.1", 200), ("3.2", 403), ("private-test", 403)])
def test_public_tv_token_scoped_to_own_room(
    room_booking_client, room_tv_headers, private_room, slot, exchange_account, target_room, status
):
    start, end = slot
    response = room_booking_client.get(
        f"/room/{target_room}/bookings", headers=room_tv_headers("3.1"), params=dt_params(start=start, end=end)
    )
    assert response.status_code == status
