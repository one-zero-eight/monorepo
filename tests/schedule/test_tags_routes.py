from fastapi.testclient import TestClient

from tests.schedule.conftest import create_tag
from tests.schedule.constants import AUTH_REQUIRED_DETAIL, SAMPLE_TAG


def test_list_tags_empty(schedule_client: TestClient):
    response = schedule_client.get("/tags/")
    assert response.status_code == 200
    assert response.json()["tags"] == []


def test_batch_create_requires_parser(schedule_client: TestClient):
    response = schedule_client.post("/tags/batch-create-or-read", json={"tags": [SAMPLE_TAG]})
    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_REQUIRED_DETAIL


def test_batch_create_or_read_idempotent(schedule_client: TestClient, parser_headers: dict[str, str]):
    first = create_tag(schedule_client, parser_headers, alias="idempotent-tag")
    second = create_tag(schedule_client, parser_headers, alias="idempotent-tag")
    assert second["id"] == first["id"]


def test_delete_by_alias_requires_parser(schedule_client: TestClient):
    response = schedule_client.delete("/tags/by-alias", params={"tag_alias": "any"})
    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_REQUIRED_DETAIL


def test_delete_by_alias(schedule_client: TestClient, parser_headers: dict[str, str]):
    create_tag(schedule_client, parser_headers, alias="delete-me-tag")
    delete_response = schedule_client.delete(
        "/tags/by-alias",
        params={"tag_alias": "delete-me-tag"},
        headers=parser_headers,
    )
    assert delete_response.status_code == 200
    list_response = schedule_client.get("/tags/")
    assert list_response.json()["tags"] == []
