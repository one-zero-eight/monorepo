import datetime as dtm

from fastapi.testclient import TestClient

from src.tabletennis.mongo import Player, Tournament


def test_games_by_id_return_creation_and_finish_time(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["d1", "d2"]:
        portal.call(
            Player(
                innohassle_id=uid, nickname=f"Player{uid}", last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC)
            ).insert
        )
    portal.call(
        Tournament(
            tour_id="dates",
            name="Dates",
            players=["d1", "d2"],
            val_games=[],
            cval_games=[],
            active=True,
            date=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        ).insert
    )

    reg = tabletennis_client.post(
        "/reg-game",
        params={"tour_id": "dates", "tip": "val", "player1_id": "d1", "player2_id": "d2"},
        headers=admin_headers,
    )
    game_id = reg.json()["game_id"]

    def fetch() -> dict:
        response = tabletennis_client.get("/get-games-by-id", params={"ids": [game_id]}, headers=admin_headers)
        assert response.status_code == 200
        return response.json()["games"][0]

    before = fetch()
    assert before["created_at"] is not None
    assert before["finished_at"] is None

    finish = tabletennis_client.post(
        "/finish-game", params={"game_id": game_id, "s1": 3, "s2": 1, "tour_id": "dates"}, headers=admin_headers
    )
    assert finish.status_code == 200

    after = fetch()
    finished_at = dtm.datetime.fromisoformat(after["finished_at"])
    assert (
        abs((dtm.datetime.now(tz=dtm.UTC) - finished_at.replace(tzinfo=finished_at.tzinfo or dtm.UTC)).total_seconds())
        < 120
    )
