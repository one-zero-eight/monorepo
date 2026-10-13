import datetime as dtm

from fastapi.testclient import TestClient

from src.tabletennis.mongo import Player


def _insert_player(client: TestClient, uid: str, rating: int = 100, status: str = "Beginner") -> None:
    portal = client.portal
    assert portal is not None
    portal.call(
        Player(
            innohassle_id=uid,
            nickname=f"Player{uid}",
            rating=rating,
            status=status,
            last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        ).insert
    )


def _get_player(client: TestClient, uid: str) -> Player:
    portal = client.portal
    assert portal is not None
    return portal.call(Player.find_one, Player.innohassle_id == uid)


def _set_rating(client: TestClient, headers: dict[str, str], uid: str, rating: int):
    return client.post("/set-rating", params={"innohassle_id": uid, "rating": rating}, headers=headers)


def test_new_player_starts_at_100():
    player = Player(innohassle_id="fresh", last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC))
    assert player.rating == 100


def test_set_rating_requires_admin(tabletennis_client: TestClient, user_headers: dict[str, str]):
    assert _set_rating(tabletennis_client, user_headers, "whoever", 300).status_code == 403


def test_set_rating_accepts_any_non_negative_value(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _insert_player(tabletennis_client, "newbie")

    assert _set_rating(tabletennis_client, admin_headers, "newbie", -1).status_code == 400
    assert _set_rating(tabletennis_client, admin_headers, "nobody", 300).status_code == 404

    for rating in (0, 37, 313):
        response = _set_rating(tabletennis_client, admin_headers, "newbie", rating)
        assert response.status_code == 200, response.text
        assert response.json()["rating"] == rating

    player = _get_player(tabletennis_client, "newbie")
    assert player.rating == 313
    assert 37 in player.ratings.values()
    assert player.status == "Beginner"


def test_set_rating_promotes_when_crossing_350(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _insert_player(tabletennis_client, "climber", rating=300)

    response = _set_rating(tabletennis_client, admin_headers, "climber", 350)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "Advanced"

    # a manual rating below 350 does not demote: the status is changed only by hand
    response = _set_rating(tabletennis_client, admin_headers, "climber", 200)
    assert response.json()["status"] == "Advanced"
    assert _get_player(tabletennis_client, "climber").rating == 200
