import datetime as dtm

from fastapi.testclient import TestClient

from src.tabletennis.mongo import Player, Tournament


def _setup(client: TestClient, tour_id: str, player_ids: list[str]) -> None:
    portal = client.portal
    assert portal is not None
    for uid in player_ids:
        portal.call(
            Player(
                innohassle_id=uid,
                nickname=f"Player{uid}",
                last_game=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
            ).insert
        )
    portal.call(
        Tournament(
            tour_id=tour_id,
            name=f"Tournament {tour_id}",
            players=player_ids,
            val_games=[],
            cval_games=[],
            active=True,
            date=dtm.datetime(2025, 1, 1, tzinfo=dtm.UTC),
        ).insert
    )


def _set_groups(client: TestClient, headers: dict[str, str], tour_id: str, groups: dict[str, list[str]]):
    return client.post("/reg-tour/set-groups", params={"tour_id": tour_id}, json=groups, headers=headers)


def _lock(client: TestClient, headers: dict[str, str], tour_id: str):
    return client.post("/reg-tour/lock-groups", params={"tour_id": tour_id}, headers=headers)


def _reg_val(client: TestClient, headers: dict[str, str], tour_id: str, p1: str, p2: str):
    return client.post(
        "/reg-game",
        params={"tour_id": tour_id, "tip": "val", "player1_id": p1, "player2_id": p2},
        headers=headers,
    )


def test_set_groups_requires_admin(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = _set_groups(tabletennis_client, user_headers, "whatever", {"A": []})
    assert response.status_code == 403


def test_groups_are_returned_with_active_tours(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _setup(tabletennis_client, "g-list", ["a1", "a2", "b1", "b2", "b3"])
    groups = {"A": ["a1", "a2"], "B": ["b1", "b2", "b3"]}

    assert _set_groups(tabletennis_client, admin_headers, "g-list", groups).status_code == 200

    tours = tabletennis_client.get("/active-tours", headers=admin_headers).json()
    tour = next(t for t in tours if t["id"] == "g-list")
    assert tour["groups"] == groups
    assert tour["groups_locked"] is False
    assert tour["qual_seeding"] == []


def test_set_groups_rejects_duplicates_and_strangers(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _setup(tabletennis_client, "g-bad", ["p1", "p2", "p3"])

    duplicate = _set_groups(tabletennis_client, admin_headers, "g-bad", {"A": ["p1", "p2"], "B": ["p2", "p3"]})
    assert duplicate.status_code == 400

    stranger = _set_groups(tabletennis_client, admin_headers, "g-bad", {"A": ["p1", "nobody"]})
    assert stranger.status_code == 400


def test_lock_requires_every_player_in_a_group_of_two(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _setup(tabletennis_client, "g-lock", ["p1", "p2", "p3"])

    _set_groups(tabletennis_client, admin_headers, "g-lock", {"A": ["p1", "p2"]})
    assert _lock(tabletennis_client, admin_headers, "g-lock").status_code == 400

    _set_groups(tabletennis_client, admin_headers, "g-lock", {"A": ["p1", "p2"], "B": ["p3"]})
    assert _lock(tabletennis_client, admin_headers, "g-lock").status_code == 400

    _set_groups(tabletennis_client, admin_headers, "g-lock", {"A": ["p1", "p2", "p3"]})
    assert _lock(tabletennis_client, admin_headers, "g-lock").status_code == 200

    assert _set_groups(tabletennis_client, admin_headers, "g-lock", {"A": ["p1", "p2", "p3"]}).status_code == 400
    add = tabletennis_client.post(
        "/reg-tour/add-player", params={"tour_id": "g-lock"}, json={"player_ids": ["p1"]}, headers=admin_headers
    )
    assert add.status_code == 400


def test_validation_games_only_inside_locked_group(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _setup(tabletennis_client, "g-val", ["a1", "a2", "b1", "b2"])
    _set_groups(tabletennis_client, admin_headers, "g-val", {"A": ["a1", "a2"], "B": ["b1", "b2"]})

    assert _reg_val(tabletennis_client, admin_headers, "g-val", "a1", "a2").status_code == 400

    assert _lock(tabletennis_client, admin_headers, "g-val").status_code == 200
    assert _reg_val(tabletennis_client, admin_headers, "g-val", "a1", "b1").status_code == 400
    assert _reg_val(tabletennis_client, admin_headers, "g-val", "a1", "a2").status_code == 200

    unlock = tabletennis_client.post("/reg-tour/unlock-groups", params={"tour_id": "g-val"}, headers=admin_headers)
    assert unlock.status_code == 400


def test_unlock_groups_before_games(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _setup(tabletennis_client, "g-unlock", ["p1", "p2"])
    _set_groups(tabletennis_client, admin_headers, "g-unlock", {"A": ["p1", "p2"]})
    _lock(tabletennis_client, admin_headers, "g-unlock")

    unlock = tabletennis_client.post("/reg-tour/unlock-groups", params={"tour_id": "g-unlock"}, headers=admin_headers)
    assert unlock.status_code == 200
    assert unlock.json()["groups_locked"] is False


def test_qual_seeding(tabletennis_client: TestClient, admin_headers: dict[str, str]):
    _setup(tabletennis_client, "g-seed", ["p1", "p2", "p3"])
    _set_groups(tabletennis_client, admin_headers, "g-seed", {"A": ["p1", "p2", "p3"]})

    def seed(ids: list[str]):
        return tabletennis_client.post(
            "/reg-tour/set-qual-seeding", params={"tour_id": "g-seed"}, json=ids, headers=admin_headers
        )

    assert seed(["p1", "p2", "p3"]).status_code == 400  # groups not locked
    _lock(tabletennis_client, admin_headers, "g-seed")

    assert seed(["p1", "p2"]).status_code == 400
    assert seed(["p1", "p1", "p2"]).status_code == 400

    response = seed(["p3", "p1", "p2"])
    assert response.status_code == 200
    assert response.json()["qual_seeding"] == ["p3", "p1", "p2"]

    assert _reg_val(tabletennis_client, admin_headers, "g-seed", "p1", "p2").status_code == 400

    cval = tabletennis_client.post(
        "/reg-game",
        params={"tour_id": "g-seed", "tip": "cval", "player1_id": "p3", "player2_id": "p2"},
        headers=admin_headers,
    )
    assert cval.status_code == 200
    assert seed(["p1", "p2", "p3"]).status_code == 400
