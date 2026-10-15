import datetime as dtm

import httpx
import pytest
import respx

from src.clients.music_room import MusicRoomClient
from src.clients.sport_v3 import SportV3Client
from src.clients.sport_v3.exceptions import ResponseValidationError


@pytest.mark.asyncio
async def test_music_room_nullable_date_query_contract():
    with respx.mock(assert_all_called=True) as mock:
        dated = mock.get("https://music.test/users/me/remaining_daily_hours", params={"date": "2026-10-15"}).respond(
            200, json=2.5
        )
        undated = mock.get("https://music.test/users/me/remaining_weekly_hours", params={}).respond(200, json=5.0)
        async with httpx.AsyncClient() as http:
            client = MusicRoomClient(http, "https://music.test", credentials={"Bearer": "test-key"})
            assert await client.users_get_remaining_daily_hours(date=dtm.date(2026, 10, 15)) == pytest.approx(2.5)
            assert await client.users_get_remaining_weekly_hours() == pytest.approx(5.0)
    assert dated.calls[0].request.headers["authorization"] == "Bearer test-key"
    assert "date" not in undated.calls[0].request.url.params


@pytest.mark.asyncio
async def test_music_room_ics_text_contract():
    content = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nEND:VCALENDAR\r\n"
    with respx.mock(assert_all_called=True) as mock:
        mock.get("https://music.test/music-room.ics").respond(
            200, text=content, headers={"Content-Type": "text/calendar"}
        )
        async with httpx.AsyncClient() as http:
            client = MusicRoomClient(http, "https://music.test")
            assert await client.root_get_music_room_ics() == content


@pytest.mark.asyncio
async def test_sport_v3_authentication_dates_and_response_validation():
    start = dtm.datetime(2026, 10, 15, tzinfo=dtm.UTC)
    end = start + dtm.timedelta(days=14)
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get("https://sport.test/api/v3/users/me/schedule").respond(200, json=[{"title": "legacy"}])
        async with httpx.AsyncClient() as http:
            client = SportV3Client(http, "https://sport.test/api/v3", credentials={"Bearer": "sport-token"})
            with pytest.raises(ResponseValidationError):
                await client.trainings_schedule_get_personal_schedule(start=start, end=end)
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer sport-token"
    assert dtm.datetime.fromisoformat(request.url.params["start"]) == start
    assert dtm.datetime.fromisoformat(request.url.params["end"]) == end
