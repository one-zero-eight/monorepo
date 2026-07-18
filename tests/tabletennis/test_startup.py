import datetime as dtm

import pytest
from fastapi.testclient import TestClient

from src.tabletennis.mongo import Game, Player, Tournament


def test_tabletennis_app_startup(tabletennis_client: TestClient):
    response = tabletennis_client.get("/openapi.json")
    assert response.status_code == 200


def test_unauthorized_returns_401(tabletennis_client: TestClient):
    response = tabletennis_client.get("/players")
    assert response.status_code == 401


def test_list_players(tabletennis_client: TestClient, user_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None

    for uid in ["test-user-1"]:
        p = Player(
            innohassle_id=uid,
            nickname=f"Player{uid}",
            last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        )
        portal.call(p.insert)

    response = tabletennis_client.get("/players", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["players"]) >= 1


def test_get_player(tabletennis_client: TestClient, user_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None

    player = Player(
        innohassle_id="test-user-1",
        nickname="TestPlayer",
        last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
    )
    portal.call(player.insert)

    response = tabletennis_client.get("/get-player", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["innohassle_id"] == "test-user-1"
    assert data["nickname"] == "TestPlayer"


def test_get_player_not_found(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = tabletennis_client.get("/get-player", headers=user_headers)
    assert response.status_code == 404


@pytest.fixture()
def seeded_games(tabletennis_client: TestClient):
    portal = tabletennis_client.portal
    assert portal is not None

    for uid in ["gplayer1", "gplayer2", "gplayer3"]:
        p = Player(
            innohassle_id=uid,
            nickname=f"Player{uid}",
            last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        )
        portal.call(p.insert)

    tour = Tournament(
        tour_id="tour-1",
        name="Test Tour",
        players=["gplayer1", "gplayer2", "gplayer3"],
        active=True,
        date=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
    )
    portal.call(tour.insert)

    for i, (p1, p2) in enumerate([("gplayer1", "gplayer2"), ("gplayer2", "gplayer3")]):
        g = Game(
            tour_id="tour-1",
            game_id=f"game-{i + 1}",
            player1_id=p1,
            player2_id=p2,
            player1_score=11,
            player2_score=7,
            finished=True,
        )
        portal.call(g.insert)


def test_list_games(tabletennis_client: TestClient, seeded_games, user_headers: dict[str, str]):
    response = tabletennis_client.get("/get-games", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_get_game_by_id(tabletennis_client: TestClient, seeded_games, user_headers: dict[str, str]):
    response = tabletennis_client.get("/get-games-by-id", params={"ids": ["game-1"]}, headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_found"] == 1
    assert data["games"][0]["game_id"] == "game-1"
    assert data["games"][0]["player1"]["score"] == 11


def test_get_game_not_found(tabletennis_client: TestClient, seeded_games, user_headers: dict[str, str]):
    response = tabletennis_client.get("/get-games-by-id", params={"ids": ["nonexistent"]}, headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_found"] == 0
    assert "nonexistent" in data["missing_ids"]
