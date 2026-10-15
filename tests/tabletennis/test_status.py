import datetime as dtm
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.tabletennis.mongo import Player, Tournament
from tests.tabletennis.conftest import TABLETENNIS_ADMIN_EMAIL


def _player(portal, uid: str, rating: int, status: str) -> None:
    portal.call(
        Player(
            innohassle_id=uid,
            nickname=f"Player{uid}",
            rating=rating,
            ratings={dtm.datetime.now(tz=dtm.UTC): rating},
            status=status,
            last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        ).insert
    )


def _tour(portal, tour_id: str, players: list[str]) -> None:
    portal.call(
        Tournament(
            tour_id=tour_id,
            name=f"Tournament {tour_id}",
            players=players,
            val_games=[],
            cval_games=[],
            active=True,
            date=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        ).insert
    )


def _get_player(portal, uid: str) -> Player:
    return portal.call(Player.find_one, Player.innohassle_id == uid)


def _play(client: TestClient, headers, tour_id: str, p1: str, p2: str, s1: int, s2: int) -> dict:
    reg = client.post(
        "/reg-game",
        params={"tour_id": tour_id, "tip": "val", "player1_id": p1, "player2_id": p2},
        headers=headers,
    )
    assert reg.status_code == 200, reg.text
    game_id = reg.json()["game_id"]
    finish = client.post(
        "/finish-game", params={"game_id": game_id, "s1": s1, "s2": s2, "tour_id": tour_id}, headers=headers
    )
    assert finish.status_code == 200, finish.text
    return finish.json()


def test_beginner_reaching_350_becomes_advanced(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "rookie", 345, "Beginner")
    _player(portal, "rookie2", 345, "Beginner")
    _tour(portal, "promo", ["rookie", "rookie2"])

    result = _play(tabletennis_client, admin_headers, "promo", "rookie", "rookie2", 3, 0)

    assert result["player1"]["league"] == "Advanced"
    assert _get_player(portal, "rookie").rating == 355
    assert _get_player(portal, "rookie2").status == "Beginner"


def test_games_do_not_take_advanced_below_350(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "edge", 352, "Advanced")
    _player(portal, "rival", 352, "Advanced")
    _player(portal, "low", 300, "Advanced")
    _player(portal, "rival2", 300, "Advanced")
    _tour(portal, "floor", ["edge", "rival"])
    _tour(portal, "floor-low", ["low", "rival2"])

    result = _play(tabletennis_client, admin_headers, "floor", "edge", "rival", 0, 3)
    assert _get_player(portal, "edge").rating == 350
    assert result["player1"]["delta"] == -2

    # rating set below 350 by hand: games keep it from dropping further
    _play(tabletennis_client, admin_headers, "floor-low", "low", "rival2", 0, 3)
    assert _get_player(portal, "low").rating == 300


def test_fix_game_takes_back_the_promotion(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "a", 345, "Beginner")
    _player(portal, "b", 345, "Beginner")
    _tour(portal, "fix-promo", ["a", "b"])

    game_id = _play(tabletennis_client, admin_headers, "fix-promo", "a", "b", 3, 0)["game_id"]
    assert _get_player(portal, "a").status == "Advanced"

    fixed = tabletennis_client.post(
        "/fix-game", params={"game_id": game_id, "s1": 0, "s2": 3, "tour_id": "fix-promo"}, headers=admin_headers
    )
    assert fixed.status_code == 200, fixed.text

    a, b = _get_player(portal, "a"), _get_player(portal, "b")
    assert (a.status, a.rating) == ("Beginner", 340)
    assert (b.status, b.rating) == ("Advanced", 355)


def test_set_status_has_no_admin_status(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "someone", 200, "Beginner")

    def set_status(status: str):
        return tabletennis_client.post(
            "/set-status", params={"innohassle_id": "someone", "status": status}, headers=admin_headers
        )

    assert set_status("admin").status_code == 422
    response = set_status("advanced")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Advanced"
    assert set_status("beginner").json()["status"] == "Beginner"


@pytest.fixture()
def admin_account(
    tabletennis_client: TestClient, inh_accounts_mock_users: dict[str, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
):
    # imported here: the settings must be loaded by the tabletennis_client fixture first
    from src.tabletennis.admin_config import reset_admin_ids_cache

    account = {
        **inh_accounts_mock_users["test-user-1"],
        "id": "tt-admin-1",
        "innopolis_info": {
            **inh_accounts_mock_users["test-user-1"]["innopolis_info"],
            "email": TABLETENNIS_ADMIN_EMAIL,
        },
    }
    monkeypatch.setitem(inh_accounts_mock_users, "tt-admin-1", account)
    reset_admin_ids_cache()
    yield
    reset_admin_ids_cache()


def test_players_mark_admins(tabletennis_client: TestClient, user_headers: dict[str, str], admin_account):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "tt-admin-1", 200, "Beginner")
    _player(portal, "test-user-1", 400, "Advanced")

    response = tabletennis_client.get("/players", headers=user_headers)
    assert response.status_code == 200
    flags = {p["innohassle_id"]: (p["is_admin"], p["status"]) for p in response.json()["players"]}
    assert flags == {"tt-admin-1": (True, "Beginner"), "test-user-1": (False, "Advanced")}
