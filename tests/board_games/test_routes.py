from fastapi.testclient import TestClient


def make_admin(board_games_client: TestClient, superadmin_headers: dict[str, str]) -> None:
    response = board_games_client.post(
        "/users/change_role",
        params={"role": "admin", "user_to_change_email": "test-user-1@innopolis.university"},
        headers=superadmin_headers,
    )
    assert response.status_code == 200


def test_user_can_see_available_games_and_reserve(
    board_games_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    make_admin(board_games_client, superadmin_headers)
    created = board_games_client.post(
        "/admin/board-games",
        json={
            "title": "Catan",
            "description": "Trade and build",
            "photo_url": "https://example.test/catan.jpg",
            "total_copies": 1,
        },
        headers=user_headers,
    )
    assert created.status_code == 200
    assert created.json()["photo_url"] == "https://example.test/catan.jpg"
    game_id = created.json()["id"]

    listed = board_games_client.get("/board-games", headers=user_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["available_copies"] == 1

    listed_admin = board_games_client.get("/admin/board-games", headers=user_headers)
    assert listed_admin.status_code == 200
    assert listed_admin.json()[0]["available_in_storage"] == 1

    reserved = board_games_client.post(
        f"/board-games/{game_id}/reservations",
        json={
            "tg_alias": "@test_user_one",
            "return_date": "2026-06-30",
            "when_available": "after June 30",
            "comments": "Please keep the box complete",
        },
        headers=user_headers,
    )
    assert reserved.status_code == 200
    assert reserved.json()["status"] == "reserved"
    assert reserved.json()["tg_alias"] == "@test_user_one"
    assert reserved.json()["return_date"] == "2026-06-30"
    assert reserved.json()["when_available"] == "after June 30"
    assert reserved.json()["comments"] == "Please keep the box complete"
    reservation_id = reserved.json()["id"]

    edited = board_games_client.patch(
        f"/users/me/reservations/{reservation_id}",
        json={
            "tg_alias": "@changed_user",
            "return_date": "2026-07-10",
            "when_available": "next week",
            "comments": "Updated note",
        },
        headers=user_headers,
    )
    assert edited.status_code == 200
    assert edited.json()["tg_alias"] == "@changed_user"
    assert edited.json()["return_date"] == "2026-07-10"
    assert edited.json()["when_available"] == "next week"
    assert edited.json()["comments"] == "Updated note"

    unavailable = board_games_client.post(f"/board-games/{game_id}/reservations", headers=user_headers)
    assert unavailable.status_code == 409
    assert unavailable.json()["detail"] == "Board game is not available"

    listed_admin_after_reservation = board_games_client.get("/admin/board-games", headers=user_headers)
    assert listed_admin_after_reservation.status_code == 200
    assert listed_admin_after_reservation.json()[0]["available_in_storage"] == 1


def test_admin_can_lend_reservation_and_see_borrower(
    board_games_client: TestClient,
    superadmin_headers: dict[str, str],
    user_headers: dict[str, str],
):
    make_admin(board_games_client, superadmin_headers)
    created = board_games_client.post(
        "/admin/board-games",
        json={"title": "Azul", "total_copies": 1},
        headers=user_headers,
    )
    assert created.status_code == 200
    assert created.json()["photo_url"] is None
    game_id = created.json()["id"]
    reservation = board_games_client.post(f"/board-games/{game_id}/reservations", headers=user_headers)
    reservation_id = reservation.json()["id"]

    current = board_games_client.get("/admin/reservations", params={"how": "current"}, headers=user_headers)

    assert current.status_code == 200
    assert current.json()[0]["id"] == reservation_id

    lent = board_games_client.patch(
        f"/admin/reservations/{reservation_id}/status",
        json={"status": "taken", "borrower_name": "Test User One"},
        headers=user_headers,
    )
    assert lent.status_code == 200
    assert lent.json()["status"] == "taken"
    assert lent.json()["borrower_name"] == "Test User One"

    edit_taken = board_games_client.patch(
        f"/users/me/reservations/{reservation_id}",
        json={"comments": "Cannot change taken reservation"},
        headers=user_headers,
    )
    assert edit_taken.status_code == 409
    assert edit_taken.json()["detail"] == "Reservation is not reserved"

    delete_taken = board_games_client.delete(f"/users/me/reservations/{reservation_id}", headers=user_headers)
    assert delete_taken.status_code == 409
    assert delete_taken.json()["detail"] == "Reservation is not reserved"

    current_after_lend = board_games_client.get("/admin/reservations", params={"how": "current"}, headers=user_headers)
    assert current_after_lend.status_code == 200
    assert current_after_lend.json()[0]["status"] == "taken"

    listed_admin_after_lend = board_games_client.get("/admin/board-games", headers=user_headers)
    assert listed_admin_after_lend.status_code == 200
    assert listed_admin_after_lend.json()[0]["available_in_storage"] == 0

    returned = board_games_client.patch(
        f"/admin/reservations/{reservation_id}/status",
        json={"status": "returned", "borrower_name": None},
        headers=user_headers,
    )
    assert returned.status_code == 200
    assert returned.json()["status"] == "returned"

    current_after_return = board_games_client.get(
        "/admin/reservations", params={"how": "current"}, headers=user_headers
    )
    assert current_after_return.status_code == 200
    assert current_after_return.json() == []

    listed_admin_after_return = board_games_client.get("/admin/board-games", headers=user_headers)
    assert listed_admin_after_return.status_code == 200
    assert listed_admin_after_return.json()[0]["available_in_storage"] == 1

    reservations = board_games_client.get("/users/me/reservations", params={"how": "all"}, headers=user_headers)
    assert reservations.status_code == 200
    assert reservations.json()[0]["borrower_name"] == "Test User One"

    edit_returned = board_games_client.patch(
        f"/users/me/reservations/{reservation_id}",
        json={"comments": "Cannot change returned reservation"},
        headers=user_headers,
    )
    assert edit_returned.status_code == 409
    assert edit_returned.json()["detail"] == "Reservation is not reserved"

    delete_returned = board_games_client.delete(f"/users/me/reservations/{reservation_id}", headers=user_headers)
    assert delete_returned.status_code == 409
    assert delete_returned.json()["detail"] == "Reservation is not reserved"

    deleted = board_games_client.delete(f"/admin/reservations/{reservation_id}", headers=user_headers)
    assert deleted.status_code == 200

    reservations_after_delete = board_games_client.get(
        "/users/me/reservations", params={"how": "all"}, headers=user_headers
    )
    assert reservations_after_delete.status_code == 200
    assert reservations_after_delete.json() == []


def test_non_admin_cannot_use_admin_routes(board_games_client: TestClient, user_headers: dict[str, str]):
    response = board_games_client.get("/admin/board-games", headers=user_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not an admin in board games service"
