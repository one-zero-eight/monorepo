import datetime as dtm

from fastapi.testclient import TestClient

from src.tabletennis.mongo import Player, Tournament


def _get_player(portal, uid: str) -> Player:
    return portal.call(Player.find_one, Player.innohassle_id == uid)


def _mk_player(uid: str, rating: int = 1000, status: str = "Beginner") -> Player:
    return Player(
        innohassle_id=uid,
        nickname=f"Player{uid}",
        rating=rating,
        ratings={dtm.datetime.now(tz=dtm.UTC): rating},
        status=status,
        last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
    )


def _mk_tournament(tour_id: str, players: list[str]) -> Tournament:
    return Tournament(
        tour_id=tour_id,
        name=f"Tournament {tour_id}",
        players=players,
        val_games=[],
        cval_games=[],
        active=True,
        date=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
    )


def _play_game(
    client: TestClient,
    admin_headers: dict[str, str],
    tour_id: str,
    p1_id: str,
    p2_id: str,
    s1: int,
    s2: int,
) -> dict:
    reg_response = client.post(
        "/reg-game",
        params={"tour_id": tour_id, "tip": "val", "player1_id": p1_id, "player2_id": p2_id},
        headers=admin_headers,
    )
    assert reg_response.status_code == 200, reg_response.text
    game_id = reg_response.json()["game_id"]

    finish_response = client.post(
        "/finish-game",
        params={"game_id": game_id, "s1": s1, "s2": s2, "tour_id": tour_id},
        headers=admin_headers,
    )
    assert finish_response.status_code == 200, finish_response.text
    return finish_response.json()


def test_finish_game_requires_admin(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = tabletennis_client.post(
        "/finish-game",
        params={"game_id": "whatever", "s1": 3, "s2": 0, "tour_id": "whatever"},
        headers=user_headers,
    )
    assert response.status_code == 403


def test_finish_game_rejects_draw(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None

    p1, p2 = _mk_player("p1"), _mk_player("p2")
    portal.call(p1.insert)
    portal.call(p2.insert)
    portal.call(_mk_tournament("tour-draw", ["p1", "p2"]).insert)

    response = tabletennis_client.post(
        "/reg-game",
        params={"tour_id": "tour-draw", "tip": "val", "player1_id": "p1", "player2_id": "p2"},
        headers=admin_headers,
    )
    game_id = response.json()["game_id"]

    response = tabletennis_client.post(
        "/finish-game",
        params={"game_id": game_id, "s1": 2, "s2": 2, "tour_id": "tour-draw"},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_finish_game_twice_is_rejected(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None

    portal.call(_mk_player("p1").insert)
    portal.call(_mk_player("p2").insert)
    portal.call(_mk_tournament("tour-twice", ["p1", "p2"]).insert)

    result = _play_game(tabletennis_client, admin_headers, "tour-twice", "p1", "p2", 3, 0)
    game_id = result["game_id"]

    response = tabletennis_client.post(
        "/finish-game",
        params={"game_id": game_id, "s1": 3, "s2": 1, "tour_id": "tour-twice"},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_finish_game_rttf_delta_between_two_advanced_players(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    """Equal 300-rated non-beginners, avg rating 300 -> k=0.25; 3-set win -> D=1.2."""
    portal = tabletennis_client.portal
    assert portal is not None

    portal.call(_mk_player("p1", rating=300, status="Advanced").insert)
    portal.call(_mk_player("p2", rating=300, status="Advanced").insert)
    portal.call(_mk_tournament("tour-adv", ["p1", "p2"]).insert)

    result = _play_game(tabletennis_client, admin_headers, "tour-adv", "p1", "p2", 3, 0)

    assert result["player1"]["delta"] == 3
    assert result["player2"]["delta"] == -3

    p1 = _get_player(portal, "p1")
    p2 = _get_player(portal, "p2")
    assert p1.rating == 303
    assert p2.rating == 297


def test_finish_game_beginner_winner_does_not_leak_coefficients_to_opponent(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    """
    Regression test: a beginner winner must not force the beginner's k/D onto a
    non-beginner opponent - the opponent keeps their own table-based coefficients.
    """
    portal = tabletennis_client.portal
    assert portal is not None

    portal.call(_mk_player("beginner", rating=300, status="Beginner").insert)
    portal.call(_mk_player("advanced", rating=300, status="Advanced").insert)
    portal.call(_mk_tournament("tour-mix", ["beginner", "advanced"]).insert)

    result = _play_game(tabletennis_client, admin_headers, "tour-mix", "beginner", "advanced", 3, 0)

    assert result["player1"]["delta"] == 10  # beginner winner: k=1, D=1 -> base 10
    assert result["player2"]["delta"] == -3  # advanced loser: k=0.25, D=1.2 -> base 10

    beginner = _get_player(portal, "beginner")
    advanced = _get_player(portal, "advanced")
    assert beginner.rating == 310
    assert advanced.rating == 297


def test_finish_game_no_delta_when_rating_gap_at_least_100(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    portal = tabletennis_client.portal
    assert portal is not None

    portal.call(_mk_player("strong", rating=1200, status="Advanced").insert)
    portal.call(_mk_player("weak", rating=1000, status="Advanced").insert)
    portal.call(_mk_tournament("tour-gap", ["strong", "weak"]).insert)

    result = _play_game(tabletennis_client, admin_headers, "tour-gap", "strong", "weak", 3, 0)

    assert result["player1"]["delta"] == 0
    assert result["player2"]["delta"] == 0

    strong = _get_player(portal, "strong")
    weak = _get_player(portal, "weak")
    assert strong.rating == 1200
    assert weak.rating == 1000


def test_finish_game_rating_never_drops_below_one(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None

    portal.call(_mk_player("p1", rating=1, status="Advanced").insert)
    portal.call(_mk_player("p2", rating=1, status="Advanced").insert)
    portal.call(_mk_tournament("tour-floor", ["p1", "p2"]).insert)

    _play_game(tabletennis_client, admin_headers, "tour-floor", "p1", "p2", 3, 0)

    loser = _get_player(portal, "p2")
    assert loser.rating >= 1


def test_tournament_bonus_requires_at_least_16_players(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    portal = tabletennis_client.portal
    assert portal is not None

    ids = ["s1", "s2", "s3"]
    for uid in ids:
        portal.call(_mk_player(uid, rating=1000, status="Advanced").insert)
    portal.call(_mk_tournament("tour-small", ids).insert)

    response = tabletennis_client.post(
        "/reg-tour/change-qual-top",
        params={"tour_id": "tour-small"},
        json={"1": "s1", "2": "s2", "3": "s3"},
        headers=admin_headers,
    )
    assert response.status_code == 200

    winner = _get_player(portal, "s1")
    assert winner.rating == 1000


def test_tournament_bonus_applies_once_even_for_below_average_prize_winners(
    tabletennis_client: TestClient, admin_headers: dict[str, str]
):
    """
    12 fillers rated 2000 set Rср12=2000. Prize winners rated 1000 are 1000 points
    BELOW that average - the "< 100" bracket has no lower bound, so they still get
    the top bonus tier. Calling change-qual-top again must not double the bonus.
    """
    portal = tabletennis_client.portal
    assert portal is not None

    filler_ids = [f"filler-{i}" for i in range(12)]
    for uid in filler_ids:
        portal.call(_mk_player(uid, rating=2000, status="Advanced").insert)

    prize_ids = ["first", "second", "third", "fourth"]
    for uid in prize_ids:
        portal.call(_mk_player(uid, rating=1000, status="Advanced").insert)

    all_ids = filler_ids + prize_ids
    portal.call(_mk_tournament("tour-bonus", all_ids).insert)

    partial_top = {"1": "first", "2": "second", "3": "third"}
    response = tabletennis_client.post(
        "/reg-tour/change-qual-top", params={"tour_id": "tour-bonus"}, json=partial_top, headers=admin_headers
    )
    assert response.status_code == 200
    # standings are incomplete: the tournament is not over, no bonus yet
    assert _get_player(portal, "first").rating == 1000

    top = {str(place): uid for place, uid in enumerate(prize_ids + filler_ids, start=1)}
    response = tabletennis_client.post(
        "/reg-tour/change-qual-top", params={"tour_id": "tour-bonus"}, json=top, headers=admin_headers
    )
    assert response.status_code == 200

    first = _get_player(portal, "first")
    second = _get_player(portal, "second")
    third = _get_player(portal, "third")
    assert first.rating == 1025  # +2.5%
    assert second.rating == 1015  # +1.5%
    assert third.rating == 1010  # +1%

    # Re-sending the same standings (change-qual-top is a full overwrite, not a patch)
    # must not grant the bonus a second time.
    response = tabletennis_client.post(
        "/reg-tour/change-qual-top", params={"tour_id": "tour-bonus"}, json=top, headers=admin_headers
    )
    assert response.status_code == 200

    first_again = _get_player(portal, "first")
    assert first_again.rating == 1025
