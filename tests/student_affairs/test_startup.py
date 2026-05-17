from fastapi.testclient import TestClient


def test_student_affairs_app_startup(student_affairs_client: TestClient):
    response = student_affairs_client.get("/openapi.json")
    assert response.status_code == 200
