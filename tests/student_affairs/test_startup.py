from fastapi.testclient import TestClient

from tests.metrics import assert_metrics_contract


def test_student_affairs_app_startup(student_affairs_client: TestClient):
    response = student_affairs_client.get("/openapi.json")
    assert response.status_code == 200
    assert_metrics_contract(student_affairs_client, "student_affairs")
