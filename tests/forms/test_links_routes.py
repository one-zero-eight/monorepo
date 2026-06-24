from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from tests.forms.constants import FORM_URL


def _create_link(forms_client: TestClient, headers: dict[str, str]) -> dict:
    response = forms_client.post("/links", json={"form_url": FORM_URL}, headers=headers)
    assert response.status_code == 200
    return response.json()


def test_create_link_requires_auth(forms_client: TestClient):
    response = forms_client.post("/links", json={"form_url": FORM_URL})
    assert response.status_code == 401
    assert response.json()["detail"] == "Credentials not provided"


def test_create_link(forms_client: TestClient, user_headers: dict[str, str]):
    body = _create_link(forms_client, user_headers)
    assert body["slug"]
    assert body["short_path"] == f"/links/{body['slug']}"


def test_create_link_dedup_same_form(forms_client: TestClient, user_headers: dict[str, str]):
    first = _create_link(forms_client, user_headers)
    second = _create_link(forms_client, user_headers)
    assert second["slug"] == first["slug"]


def test_list_links(forms_client: TestClient, user_headers: dict[str, str]):
    created = _create_link(forms_client, user_headers)
    response = forms_client.get("/links", headers=user_headers)
    assert response.status_code == 200
    slugs = {item["slug"] for item in response.json()}
    assert created["slug"] in slugs


def test_resolve_link(forms_client: TestClient, user_headers: dict[str, str]):
    created = _create_link(forms_client, user_headers)
    response = forms_client.get(f"/links/{created['slug']}", headers=user_headers)
    assert response.status_code == 200
    resolved_url = response.json()["url"]
    query = parse_qs(urlparse(resolved_url).query)
    assert "email" in query
    assert "s" in query
    assert query["email"][0] == "test-user-1@innopolis.university"


def test_verify_resolved_signature_roundtrip(forms_client: TestClient, user_headers: dict[str, str]):
    created = _create_link(forms_client, user_headers)
    resolve_response = forms_client.get(f"/links/{created['slug']}", headers=user_headers)
    resolved_url = resolve_response.json()["url"]
    signature = parse_qs(urlparse(resolved_url).query)["s"][0]

    verify_response = forms_client.post("/links/verify", json={"s": signature})
    assert verify_response.status_code == 200
    body = verify_response.json()
    assert body["valid"] is True
    assert body["payload"]["email"] == "test-user-1@innopolis.university"
    assert body["payload"]["fio"] == "Test User One"
    assert body["payload"]["telegram"] == "@test_user_one"


def test_delete_link(forms_client: TestClient, user_headers: dict[str, str]):
    created = _create_link(forms_client, user_headers)
    delete_response = forms_client.delete(f"/links/{created['slug']}", headers=user_headers)
    assert delete_response.status_code == 200

    get_response = forms_client.get(f"/links/{created['slug']}", headers=user_headers)
    assert get_response.status_code == 404


def test_delete_link_other_user_not_found(
    forms_client: TestClient,
    user_headers: dict[str, str],
    auth_header_factory,
):
    created = _create_link(forms_client, user_headers)
    other_headers = auth_header_factory("superadmin-1", "admin@innopolis.university")
    response = forms_client.delete(f"/links/{created['slug']}", headers=other_headers)
    assert response.status_code == 404


def test_create_link_invalid_form_url(forms_client: TestClient, user_headers: dict[str, str]):
    response = forms_client.post(
        "/links",
        json={"form_url": "https://evil.example/u/0123456789abcdef"},
        headers=user_headers,
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "URL host is not allowed"
