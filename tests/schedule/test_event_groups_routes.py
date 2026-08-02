from fastapi.testclient import TestClient

from tests.schedule.conftest import create_event_group
from tests.schedule.constants import AUTH_REQUIRED_DETAIL, SAMPLE_EVENT_GROUP


def test_create_requires_parser(schedule_client: TestClient):
    response = schedule_client.post("/event-groups/", json=SAMPLE_EVENT_GROUP)
    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_REQUIRED_DETAIL


def test_create_and_read_by_alias(schedule_client: TestClient, parser_headers: dict[str, str]):
    created = create_event_group(schedule_client, parser_headers, alias="read-by-alias-group")
    response = schedule_client.get("/event-groups/by-alias", params={"alias": "read-by-alias-group"})
    assert response.status_code == 200
    body = response.json()
    assert body["alias"] == created["alias"]
    assert body["name"] == created["name"]


def test_read_by_alias_not_found(schedule_client: TestClient):
    response = schedule_client.get("/event-groups/by-alias", params={"alias": "missing-group"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Event group not found"


def test_list_event_groups(schedule_client: TestClient, parser_headers: dict[str, str]):
    created = create_event_group(schedule_client, parser_headers, alias="listed-group")
    response = schedule_client.get("/event-groups/")
    assert response.status_code == 200
    aliases = {group["alias"] for group in response.json()["event_groups"]}
    assert created["alias"] in aliases


def test_update_event_group(schedule_client: TestClient, parser_headers: dict[str, str]):
    created = create_event_group(schedule_client, parser_headers, alias="update-me-group")
    response = schedule_client.put(
        f"/event-groups/{created['id']}",
        json={"name": "Updated Name"},
        headers=parser_headers,
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Name"


def test_batch_create_or_read(schedule_client: TestClient, parser_headers: dict[str, str]):
    groups = [
        {**SAMPLE_EVENT_GROUP, "alias": "batch-group-a"},
        {**SAMPLE_EVENT_GROUP, "alias": "batch-group-b"},
    ]
    first = schedule_client.post(
        "/event-groups/batch-create-or-read",
        json={"event_groups": groups},
        headers=parser_headers,
    )
    assert first.status_code == 201
    first_ids = {group["id"] for group in first.json()["event_groups"]}
    assert len(first_ids) == 2

    second = schedule_client.post(
        "/event-groups/batch-create-or-read",
        json={"event_groups": groups},
        headers=parser_headers,
    )
    assert second.status_code == 201
    second_ids = {group["id"] for group in second.json()["event_groups"]}
    assert second_ids == first_ids
