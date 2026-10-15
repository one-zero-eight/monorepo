import datetime as dtm

from fastapi.testclient import TestClient

from src.tabletennis.mongo import Game, Player, Tournament


def _player(portal, uid: str, rating: int = 300, wins: int = 0) -> None:
    portal.call(
        Player(
            innohassle_id=uid,
            nickname=f"Player{uid}",
            rating=rating,
            ratings={dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC): rating},
            wins=wins,
            last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        ).insert
    )


def _find_player(portal, uid: str) -> Player | None:
    return portal.call(Player.find_one, Player.innohassle_id == uid)


def _get_player(portal, uid: str) -> Player:
    player = _find_player(portal, uid)
    assert player is not None
    return player


def _get_tour(portal, tour_id: str) -> Tournament:
    tour = portal.call(Tournament.find_one, Tournament.tour_id == tour_id)
    assert tour is not None
    return tour


def _create_tour(client: TestClient, headers, player_ids: list[str]):
    return client.post("/reg-tour", params={"name": "Cup"}, json={"player_ids": player_ids}, headers=headers)


def _create_guest(client: TestClient, headers, nickname: str, rating: int = 100) -> str:
    response = client.post("/guests", params={"nickname": nickname, "rating": rating}, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["innohassle_id"]


def _play(client: TestClient, headers, tour_id: str, p1: str, p2: str, s1: int, s2: int) -> str:
    game = client.post(
        "/reg-game",
        params={"tour_id": tour_id, "tip": "cval", "player1_id": p1, "player2_id": p2},
        headers=headers,
    )
    assert game.status_code == 200, game.text
    game_id = game.json()["game_id"]
    finish = client.post(
        "/finish-game", params={"game_id": game_id, "s1": s1, "s2": s2, "tour_id": tour_id}, headers=headers
    )
    assert finish.status_code == 200, finish.text
    return game_id


def test_tournament_is_not_created_when_a_player_is_missing(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)

    response = _create_tour(tabletennis_client, admin_headers, ["a", "b", "nobody"])

    assert response.status_code == 400
    failed = response.json()["detail"]["failed"]
    assert [(f["identifier"], f["code"]) for f in failed] == [("nobody", "not_found")]
    assert portal.call(Tournament.find_all().to_list) == []


def test_add_player_adds_nobody_when_one_fails(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b", "c"]:
        _player(portal, uid)
    tour_id = _create_tour(tabletennis_client, admin_headers, ["a", "b"]).json()["tournament_id"]

    response = tabletennis_client.post(
        "/reg-tour/add-player", params={"tour_id": tour_id}, json={"player_ids": ["c", "a", "x"]}, headers=admin_headers
    )

    assert response.status_code == 400
    codes = {f["identifier"]: f["code"] for f in response.json()["detail"]["failed"]}
    assert codes == {"a": "already_in_tournament", "x": "not_found"}
    assert _get_tour(portal, tour_id).players == ["a", "b"]


def test_guest_plays_in_tournaments_and_is_merged_into_a_new_player(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "opp", rating=300)
    _player(portal, "newbie", rating=100)
    guest_id = _create_guest(tabletennis_client, admin_headers, "Vasya", rating=320)
    assert _get_player(portal, guest_id).placeholder

    tours = [_create_tour(tabletennis_client, admin_headers, [guest_id, "opp"]).json()["tournament_id"] for _ in "12"]
    game_ids = [_play(tabletennis_client, admin_headers, t, guest_id, "opp", 3, 1) for t in tours]
    guest_rating = _get_player(portal, guest_id).rating

    response = tabletennis_client.post(
        "/merge-guest", params={"guest_id": guest_id, "player_id": "newbie"}, headers=admin_headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["tournaments"] == 2
    assert _find_player(portal, guest_id) is None
    newbie = _get_player(portal, "newbie")
    assert (newbie.rating, newbie.wins) == (guest_rating, 2)
    for tour_id in tours:
        tour = _get_tour(portal, tour_id)
        assert tour.players == ["newbie", "opp"]
        assert (tour.cval_games or [])[0].player1_id == "newbie"
    for game_id in game_ids:
        game = portal.call(Game.find_one, Game.game_id == game_id)
        assert game is not None
        assert game.player1_id == "newbie"


def test_merge_adds_guest_games_to_a_player_who_already_played(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "opp", rating=300)
    _player(portal, "veteran", rating=250, wins=5)
    guest_id = _create_guest(tabletennis_client, admin_headers, "Petya", rating=300)
    tour_id = _create_tour(tabletennis_client, admin_headers, [guest_id, "opp"]).json()["tournament_id"]
    _play(tabletennis_client, admin_headers, tour_id, guest_id, "opp", 3, 0)
    gained = _get_player(portal, guest_id).rating - 300

    response = tabletennis_client.post(
        "/merge-guest", params={"guest_id": guest_id, "player_id": "veteran"}, headers=admin_headers
    )

    assert response.status_code == 200, response.text
    veteran = _get_player(portal, "veteran")
    assert (veteran.rating, veteran.wins) == (250 + gained, 6)


def test_merge_is_refused_when_guest_and_player_share_a_tournament(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None
    _player(portal, "real")
    guest_id = _create_guest(tabletennis_client, admin_headers, "Twin")
    _create_tour(tabletennis_client, admin_headers, [guest_id, "real"])

    response = tabletennis_client.post(
        "/merge-guest", params={"guest_id": guest_id, "player_id": "real"}, headers=admin_headers
    )

    assert response.status_code == 400
    assert _find_player(portal, guest_id) is not None


def test_merge_requires_a_guest(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)

    response = tabletennis_client.post(
        "/merge-guest", params={"guest_id": "a", "player_id": "b"}, headers=admin_headers
    )

    assert response.status_code == 404


def test_archived_tournament_can_be_reopened(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    tour_id = _create_tour(tabletennis_client, admin_headers, ["a", "b"]).json()["tournament_id"]
    tabletennis_client.post("/finish-tour", params={"tour_id": tour_id}, headers=admin_headers)

    response = tabletennis_client.post("/reopen-tour", params={"tour_id": tour_id}, headers=admin_headers)

    assert response.status_code == 200
    assert _get_tour(portal, tour_id).active
    again = tabletennis_client.post("/reopen-tour", params={"tour_id": tour_id}, headers=admin_headers)
    assert again.status_code == 400


def test_score_is_limited_to_four_sets(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None
    for uid in ["a", "b"]:
        _player(portal, uid)
    tour_id = _create_tour(tabletennis_client, admin_headers, ["a", "b"]).json()["tournament_id"]
    game_id = tabletennis_client.post(
        "/reg-game",
        params={"tour_id": tour_id, "tip": "cval", "player1_id": "a", "player2_id": "b"},
        headers=admin_headers,
    ).json()["game_id"]

    too_many = tabletennis_client.post(
        "/finish-game", params={"game_id": game_id, "s1": 5, "s2": 1, "tour_id": tour_id}, headers=admin_headers
    )
    best_of_seven = tabletennis_client.post(
        "/finish-game", params={"game_id": game_id, "s1": 4, "s2": 3, "tour_id": tour_id}, headers=admin_headers
    )

    assert too_many.status_code == 400
    assert best_of_seven.status_code == 200
