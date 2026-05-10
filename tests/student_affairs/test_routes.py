import httpx
import respx
from fastapi.testclient import TestClient


def test_student_affairs_startup_openapi(student_affairs_client: TestClient):
    response = student_affairs_client.get("/openapi.json")
    assert response.status_code == 200


def test_generate_link_requires_auth(student_affairs_client: TestClient):
    response = student_affairs_client.post("/sso/generate-link")
    assert response.status_code == 401
    assert response.json()["detail"] == "Credentials not provided"


def test_generate_link_rejects_malformed_token(student_affairs_client: TestClient):
    response = student_affairs_client.post(
        "/sso/generate-link",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Unable to verify credentials"


def test_generate_link_returns_400_when_accounts_user_missing(
    student_affairs_client: TestClient,
    inh_accounts_mock_users: dict,
    make_user_token,
):
    popped = inh_accounts_mock_users.pop("test-user-1", None)
    try:
        token = make_user_token(uid="test-user-1", email="test-user-1@innopolis.university")
        response = student_affairs_client.post(
            "/sso/generate-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "User not found"
    finally:
        if popped is not None:
            inh_accounts_mock_users["test-user-1"] = popped


def test_generate_link_success(
    student_affairs_client: TestClient,
    make_user_token,
):
    from src.student_affairs import routes as student_affairs_routes

    token = make_user_token(uid="test-user-1", email="test-user-1@innopolis.university")
    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.get(url__startswith=student_affairs_routes.omnidesk_jwt_access_base_url).mock(
            return_value=httpx.Response(200, text="https://student-affairs.omnidesk.ru/sso-redirect")
        )
        response = student_affairs_client.post(
            "/sso/generate-link",
            params={"return_to": "https://example.com/return"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert route.called
    assert response.status_code == 200
    assert response.json() == "https://student-affairs.omnidesk.ru/sso-redirect"


def test_generate_link_bubbles_omnidesk_http_error(
    student_affairs_client: TestClient,
    make_user_token,
):
    from src.student_affairs import routes as student_affairs_routes

    token = make_user_token(uid="test-user-1", email="test-user-1@innopolis.university")
    with respx.mock(assert_all_called=True) as respx_mock:
        route = respx_mock.get(url__startswith=student_affairs_routes.omnidesk_jwt_access_base_url).mock(
            return_value=httpx.Response(502)
        )
        response = student_affairs_client.post(
            "/sso/generate-link",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert route.called
    assert response.status_code == 500
