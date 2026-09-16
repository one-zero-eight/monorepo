import datetime as dtm

from fastapi.testclient import TestClient

from src.tabletennis.mongo import Player


def _insert_player(client: TestClient, uid: str) -> None:
    portal = client.portal
    assert portal is not None
    portal.call(
        Player(innohassle_id=uid, nickname=f"Player{uid}", last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC)).insert
    )


def _set_rating(client: TestClient, headers: dict[str, str], uid: str, rating: int):
    return client.post("/set-rating", params={"innohassle_id": uid, "rating": rating}, headers=headers)


def test_new_player_starts_at_rttf_minimum():
    player = Player(innohassle_id="fresh", last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC))
    assert player.rating == 100


def test_set_rating_requires_admin(tabletennis_client: TestClient, user_headers: dict[str, str]):
    assert _set_rating(tabletennis_client, user_headers, "whoever", 300).status_code == 403


def test_set_rating_follows_rttf_rules(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _insert_player(tabletennis_client, "newbie")

    assert _set_rating(tabletennis_client, admin_headers, "newbie", 75).status_code == 400  # below 100
    assert _set_rating(tabletennis_client, admin_headers, "newbie", 310).status_code == 400  # not a multiple of 25
    assert _set_rating(tabletennis_client, admin_headers, "nobody", 300).status_code == 404

    response = _set_rating(tabletennis_client, admin_headers, "newbie", 325)
    assert response.status_code == 200, response.text
    assert response.json()["rating"] == 325

    portal = tabletennis_client.portal
    assert portal is not None
    player = portal.call(Player.find_one, Player.innohassle_id == "newbie")
    assert player.rating == 325
    assert 325 in player.ratings.values()
