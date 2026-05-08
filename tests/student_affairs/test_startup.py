from fastapi.testclient import TestClient


def test_student_affairs_app_startup():
    from src.student_affairs import app as student_affairs_app

    with TestClient(student_affairs_app.app, raise_server_exceptions=False) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
