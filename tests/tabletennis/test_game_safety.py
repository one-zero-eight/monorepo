import datetime as dtm

import pytest
from fastapi.testclient import TestClient

from src.tabletennis.mongo import Game, Player, Tournament


def _player(portal, uid: str, rating: int = 500) -> None:
    portal.call(
        Player(
            innohassle_id=uid,
            nickname=f"Player{uid}",
            rating=rating,
            ratings={dtm.datetime.now(tz=dtm.UTC): rating},
            status="Advanced",
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


def _get_tour(portal, tour_id: str) -> Tournament:
    return portal.call(Tournament.find_one, Tournament.tour_id == tour_id)


def _reg(client: TestClient, headers, tour_id: str, p1: str, p2: str, tip: str = "val"):
    return client.post(
        "/reg-game",
        params={"tour_id": tour_id, "tip": tip, "player1_id": p1, "player2_id": p2},
        headers=headers,
    )


def _finish(client: TestClient, headers, tour_id: str, game_id: str, s1: int, s2: int):
    return client.post(
        "/finish-game", params={"game_id": game_id, "s1": s1, "s2": s2, "tour_id": tour_id}, headers=headers
    )


def test_second_game_for_same_pair_is_rejected(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "dup", ["a", "b"])

    assert _reg(tabletennis_client, admin_headers, "dup", "a", "b").status_code == 200
    assert _reg(tabletennis_client, admin_headers, "dup", "b", "a").status_code == 409
    # the same pair may still meet in the other stage
    assert _reg(tabletennis_client, admin_headers, "dup", "a", "b", tip="cval").status_code == 200

    tour = _get_tour(portal, "dup")
    assert len(tour.val_games or []) == 1
    assert len(tour.cval_games or []) == 1


def test_games_survive_other_admin_writes(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    """Tournament writes are partial updates: changing groups/players must not wipe registered games."""
    portal = tabletennis_client.portal
    for uid in ["a", "b", "c"]:
        _player(portal, uid)
    _tour(portal, "keep", ["a", "b"])

    game_id = _reg(tabletennis_client, admin_headers, "keep", "a", "b").json()["game_id"]
    add = tabletennis_client.post(
        "/reg-tour/add-player", params={"tour_id": "keep"}, json={"player_ids": ["c"]}, headers=admin_headers
    )
    assert add.status_code == 200
    assert _finish(tabletennis_client, admin_headers, "keep", game_id, 3, 1).status_code == 200

    tour = _get_tour(portal, "keep")
    assert tour.players == ["a", "b", "c"]
    val_games = tour.val_games or []
    assert [g.game_id for g in val_games] == [game_id]
    assert val_games[0].finished is True

    games = tabletennis_client.get("/get-games-by-id", params={"ids": [game_id]}, headers=admin_headers).json()
    assert games["games"][0]["finished"] is True
    assert games["games"][0]["player1"]["score"] == 3


def test_game_cannot_be_finished_twice(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "twice", ["a", "b"])

    game_id = _reg(tabletennis_client, admin_headers, "twice", "a", "b").json()["game_id"]
    assert _finish(tabletennis_client, admin_headers, "twice", game_id, 3, 0).status_code == 200
    rating_after_first = _get_player(portal, "a").rating

    assert _finish(tabletennis_client, admin_headers, "twice", game_id, 3, 0).status_code == 400
    assert _get_player(portal, "a").rating == rating_after_first


def test_fix_game_rolls_back_the_old_result(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "a", 500)
    _player(portal, "b", 500)
    _player(portal, "c", 500)
    _player(portal, "d", 500)
    _tour(portal, "fix", ["a", "b"])
    _tour(portal, "ref", ["c", "d"])

    # reference: b wins straight away
    ref_id = _reg(tabletennis_client, admin_headers, "ref", "c", "d").json()["game_id"]
    _finish(tabletennis_client, admin_headers, "ref", ref_id, 1, 3)

    # mistake: a entered as the winner, then corrected to b winning 3:1
    game_id = _reg(tabletennis_client, admin_headers, "fix", "a", "b").json()["game_id"]
    _finish(tabletennis_client, admin_headers, "fix", game_id, 3, 1)
    fixed = tabletennis_client.post(
        "/fix-game", params={"game_id": game_id, "s1": 1, "s2": 3, "tour_id": "fix"}, headers=admin_headers
    )
    assert fixed.status_code == 200, fixed.text

    a, b = _get_player(portal, "a"), _get_player(portal, "b")
    c, d = _get_player(portal, "c"), _get_player(portal, "d")
    assert (a.rating, b.rating) == (c.rating, d.rating)
    assert (a.wins, a.losses, b.wins, b.losses) == (0, 1, 1, 0)

    fixed_game = (_get_tour(portal, "fix").val_games or [])[0]
    assert (fixed_game.player1_score, fixed_game.player2_score) == (1, 3)
    db_game = portal.call(Game.find_one, Game.game_id == game_id)
    assert (db_game.player1_score, db_game.player2_score) == (1, 3)


def test_fix_game_rules(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "rules", ["a", "b"])

    def fix(game_id: str, s1: int, s2: int):
        return tabletennis_client.post(
            "/fix-game", params={"game_id": game_id, "s1": s1, "s2": s2, "tour_id": "rules"}, headers=admin_headers
        )

    game_id = _reg(tabletennis_client, admin_headers, "rules", "a", "b").json()["game_id"]
    assert fix(game_id, 3, 1).status_code == 400  # not finished yet

    _finish(tabletennis_client, admin_headers, "rules", game_id, 3, 1)
    assert fix(game_id, 2, 2).status_code == 400  # draw

    seeding = tabletennis_client.post(
        "/reg-tour/set-qual-seeding", params={"tour_id": "rules"}, json=["a", "b"], headers=admin_headers
    )
    assert seeding.status_code == 200
    assert fix(game_id, 1, 3).status_code == 400  # group games are frozen once qualification started


def test_fix_game_refuses_games_without_stored_deltas(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    legacy = Game(
        tour_id="legacy", game_id="old-game", player1_id="a", player2_id="b", player1_score=3, player2_score=0
    )
    legacy.finished = True
    portal.call(
        Tournament(
            tour_id="legacy",
            name="legacy",
            players=["a", "b"],
            val_games=[legacy],
            cval_games=[],
            active=True,
            date=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        ).insert
    )

    response = tabletennis_client.post(
        "/fix-game", params={"game_id": "old-game", "s1": 0, "s2": 3, "tour_id": "legacy"}, headers=admin_headers
    )
    assert response.status_code == 400


def test_cancel_game(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "cancel", ["a", "b"])

    def cancel(game_id: str):
        return tabletennis_client.post(
            "/cancel-game", params={"game_id": game_id, "tour_id": "cancel"}, headers=admin_headers
        )

    game_id = _reg(tabletennis_client, admin_headers, "cancel", "a", "b").json()["game_id"]
    assert cancel(game_id).status_code == 200
    assert _get_tour(portal, "cancel").val_games == []
    assert portal.call(Game.find_one, Game.game_id == game_id) is None

    # the pair can start again after a cancel, but a finished game can't be cancelled
    game_id = _reg(tabletennis_client, admin_headers, "cancel", "a", "b").json()["game_id"]
    _finish(tabletennis_client, admin_headers, "cancel", game_id, 3, 2)
    assert cancel(game_id).status_code == 400


def test_bonus_is_not_granted_through_val_top(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    ids = [f"v{i}" for i in range(16)]
    for uid in ids:
        _player(portal, uid, 1000)
    _tour(portal, "valtop", ids)

    top = {str(i + 1): uid for i, uid in enumerate(ids)}
    response = tabletennis_client.post(
        "/reg-tour/change-val-top", params={"tour_id": "valtop"}, json=top, headers=admin_headers
    )
    assert response.status_code == 200
    assert _get_player(portal, "v0").rating == 1000


def test_finish_game_rejects_invalid_scores(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "bad", ["a", "b"])

    game_id = _reg(tabletennis_client, admin_headers, "bad", "a", "b").json()["game_id"]
    for s1, s2 in [(-1, 3), (3, -2), (10, 0), (3, 10), (2, 2)]:
        assert _finish(tabletennis_client, admin_headers, "bad", game_id, s1, s2).status_code == 400, (s1, s2)

    game = (_get_tour(portal, "bad").val_games or [])[0]
    assert not game.finished
    assert _get_player(portal, "a").rating == 500
    assert _get_player(portal, "b").rating == 500
    # the game can still be finished with a valid score
    assert _finish(tabletennis_client, admin_headers, "bad", game_id, 9, 0).status_code == 200


def test_fix_game_rejects_invalid_scores(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "badfix", ["a", "b"])

    game_id = _reg(tabletennis_client, admin_headers, "badfix", "a", "b").json()["game_id"]
    _finish(tabletennis_client, admin_headers, "badfix", game_id, 3, 1)
    rating_a = _get_player(portal, "a").rating

    for s1, s2 in [(-1, 3), (1, -3), (12, 1), (1, 12)]:
        fixed = tabletennis_client.post(
            "/fix-game", params={"game_id": game_id, "s1": s1, "s2": s2, "tour_id": "badfix"}, headers=admin_headers
        )
        assert fixed.status_code == 400, (s1, s2)

    game = (_get_tour(portal, "badfix").val_games or [])[0]
    assert (game.player1_score, game.player2_score) == (3, 1)
    assert _get_player(portal, "a").rating == rating_a


def test_failed_rating_save_leaves_game_unfinished(
    tabletennis_client: TestClient, admin_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    """Ratings and the game result are saved together: a crash in between must not finish the game."""
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    _tour(portal, "crash", ["a", "b"])
    game_id = _reg(tabletennis_client, admin_headers, "crash", "a", "b").json()["game_id"]

    original_save = Player.save
    calls = 0

    async def failing_save(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:  # the first player is already saved when the second one fails
            raise RuntimeError("database is gone")
        return await original_save(self, *args, **kwargs)

    monkeypatch.setattr(Player, "save", failing_save)
    with pytest.raises(RuntimeError):
        _finish(tabletennis_client, admin_headers, "crash", game_id, 3, 0)
    monkeypatch.setattr(Player, "save", original_save)

    assert not (_get_tour(portal, "crash").val_games or [])[0].finished
    assert not portal.call(Game.find_one, Game.game_id == game_id).finished
    a, b = _get_player(portal, "a"), _get_player(portal, "b")
    assert (a.rating, a.wins, b.rating, b.losses) == (500, 0, 500, 0)

    # nothing was half-saved, so the game can be finished again
    assert _finish(tabletennis_client, admin_headers, "crash", game_id, 3, 0).status_code == 200
    assert _get_player(portal, "a").wins == 1
