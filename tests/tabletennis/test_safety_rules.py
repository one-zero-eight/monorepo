import datetime as dtm
from typing import Any

from fastapi.testclient import TestClient

from src.tabletennis.mongo import Game, Player, Tournament


def _player(portal, uid: str) -> None:
    portal.call(
        Player(
            innohassle_id=uid, nickname=f"Player{uid}", rating=300, last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC)
        ).insert
    )


def _tour(portal, tour_id: str, players: list[str], **fields: Any) -> None:
    tour = Tournament(
        tour_id=tour_id,
        name=f"Tournament {tour_id}",
        players=players,
        val_games=[],
        cval_games=[],
        active=True,
        date=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
    )
    for name, value in fields.items():
        setattr(tour, name, value)
    portal.call(tour.insert)


def _find_tour(portal, tour_id: str) -> Tournament | None:
    return portal.call(Tournament.find_one, Tournament.tour_id == tour_id)


def _get_tour(portal, tour_id: str) -> Tournament:
    tour = _find_tour(portal, tour_id)
    assert tour is not None
    return tour


def _reg(client: TestClient, headers, tour_id: str, p1: str, p2: str, tip: str = "cval"):
    return client.post(
        "/reg-game",
        params={"tour_id": tour_id, "tip": tip, "player1_id": p1, "player2_id": p2},
        headers=headers,
    )


def _finish(client: TestClient, headers, tour_id: str, game_id: str, s1: int, s2: int):
    return client.post(
        "/finish-game", params={"game_id": game_id, "s1": s1, "s2": s2, "tour_id": tour_id}, headers=headers
    )


def _fix(client: TestClient, headers, tour_id: str, game_id: str, s1: int, s2: int):
    return client.post(
        "/fix-game", params={"game_id": game_id, "s1": s1, "s2": s2, "tour_id": tour_id}, headers=headers
    )


def _play(client: TestClient, headers, tour_id: str, p1: str, p2: str, s1: int, s2: int, tip: str = "cval") -> str:
    game_id = _reg(client, headers, tour_id, p1, p2, tip).json()["game_id"]
    assert _finish(client, headers, tour_id, game_id, s1, s2).status_code == 200
    return game_id


def test_finished_tournament_cannot_be_changed(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "done", ["a", "b"])
    game_id = _reg(tabletennis_client, admin_headers, "done", "a", "b").json()["game_id"]
    tabletennis_client.post("/finish-tour", params={"tour_id": "done"}, headers=admin_headers)

    assert _reg(tabletennis_client, admin_headers, "done", "b", "a", "val").status_code == 400
    assert _finish(tabletennis_client, admin_headers, "done", game_id, 3, 1).status_code == 400
    cancel = tabletennis_client.post(
        "/cancel-game", params={"game_id": game_id, "tour_id": "done"}, headers=admin_headers
    )
    assert cancel.status_code == 400


def test_seeding_waits_for_group_games_in_progress(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "seed", ["a", "b"], groups={"A": ["a", "b"]}, groups_locked=True)
    _reg(tabletennis_client, admin_headers, "seed", "a", "b", "val")

    response = tabletennis_client.post(
        "/reg-tour/set-qual-seeding", params={"tour_id": "seed"}, json=["a", "b"], headers=admin_headers
    )

    assert response.status_code == 400
    assert _get_tour(portal, "seed").qual_seeding == []


def test_group_game_cannot_be_finished_after_qualification_started(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    open_game = Game(tour_id="late", game_id="g-open", player1_id="a", player2_id="b", player1_score=0, player2_score=0)
    _tour(
        portal,
        "late",
        ["a", "b"],
        groups={"A": ["a", "b"]},
        groups_locked=True,
        qual_seeding=["a", "b"],
        val_games=[open_game],
    )
    portal.call(open_game.model_copy().insert)

    assert _finish(tabletennis_client, admin_headers, "late", "g-open", 3, 1).status_code == 400


def test_bracket_winner_is_fixed_once_the_next_match_started(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b", "c", "d"]:
        _player(portal, uid)
    _tour(portal, "br", ["a", "b", "c", "d"])
    semi = _play(tabletennis_client, admin_headers, "br", "a", "d", 3, 1)
    _play(tabletennis_client, admin_headers, "br", "b", "c", 3, 2)
    _reg(tabletennis_client, admin_headers, "br", "a", "b")

    assert _fix(tabletennis_client, admin_headers, "br", semi, 1, 3).status_code == 400
    assert _fix(tabletennis_client, admin_headers, "br", semi, 3, 0).status_code == 200


def test_bracket_winner_can_change_before_the_next_match(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "br2", ["a", "b"])
    game_id = _play(tabletennis_client, admin_headers, "br2", "a", "b", 3, 1)

    assert _fix(tabletennis_client, admin_headers, "br2", game_id, 1, 3).status_code == 200


def test_my_games_returns_only_own_games(
    tabletennis_client: TestClient, admin_headers: dict[str, str], auth_header_factory
):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["me", "b", "c"]:
        _player(portal, uid)
    _tour(portal, "mine", ["me", "b", "c"])
    mine = _play(tabletennis_client, admin_headers, "mine", "me", "b", 3, 0)
    _play(tabletennis_client, admin_headers, "mine", "b", "c", 3, 0)

    response = tabletennis_client.get("/my-games", headers=auth_header_factory("me", "me@innopolis.university"))

    assert response.status_code == 200
    assert [g["game_id"] for g in response.json()["games"]] == [mine]


def test_tournament_without_finished_games_can_be_deleted(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "oops", ["a", "b"])
    game_id = _reg(tabletennis_client, admin_headers, "oops", "a", "b").json()["game_id"]

    response = tabletennis_client.post("/delete-tour", params={"tour_id": "oops"}, headers=admin_headers)

    assert response.status_code == 200
    assert _find_tour(portal, "oops") is None
    assert portal.call(Game.find_one, Game.game_id == game_id) is None


def test_tournament_with_finished_games_cannot_be_deleted(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "real", ["a", "b"])
    _play(tabletennis_client, admin_headers, "real", "a", "b", 3, 0)

    response = tabletennis_client.post("/delete-tour", params={"tour_id": "real"}, headers=admin_headers)

    assert response.status_code == 400
    assert _find_tour(portal, "real") is not None


def test_tournament_name_must_not_be_blank(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)

    response = tabletennis_client.post(
        "/reg-tour", params={"name": "   "}, json={"player_ids": ["a", "b"]}, headers=admin_headers
    )

    assert response.status_code == 400
    assert portal.call(Tournament.find_all().to_list) == []
