from fastapi.testclient import TestClient


def test_tabletennis_app_startup(tabletennis_client: TestClient):
    response = tabletennis_client.get("/openapi.json")
    assert response.status_code == 200


def test_list_players(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = tabletennis_client.get("/players/", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 3


def test_get_player(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = tabletennis_client.get("/players/1", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Alice"


def test_get_player_not_found(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = tabletennis_client.get("/players/999", headers=user_headers)
    assert response.status_code == 404


def test_list_games(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = tabletennis_client.get("/games/", headers=user_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_get_game(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = tabletennis_client.get("/games/1", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["player1_id"] == "1"


def test_get_game_not_found(tabletennis_client: TestClient, user_headers: dict[str, str]):
    response = tabletennis_client.get("/games/999", headers=user_headers)
    assert response.status_code == 404


def test_unauthorized_returns_401(tabletennis_client: TestClient):
    response = tabletennis_client.get("/players/")
    assert response.status_code == 401
