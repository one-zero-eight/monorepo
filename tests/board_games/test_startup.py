from fastapi.testclient import TestClient


def test_board_games_app_startup(board_games_client: TestClient):
    response = board_games_client.get("/openapi.json")

    assert response.status_code == 200
