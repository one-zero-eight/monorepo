from fastapi.testclient import TestClient

from tests.schedule.constants import AUTH_REQUIRED_DETAIL


def test_get_predefined_requires_parser(schedule_client: TestClient):
    response = schedule_client.get("/get-predefined-data")
    assert response.status_code == 401
    assert response.json()["detail"] == AUTH_REQUIRED_DETAIL


def test_update_and_get_predefined(schedule_client: TestClient, parser_headers: dict[str, str]):
    payload = {
        "users": [{"email": "student@innopolis.university", "groups": ["group-a"]}],
        "academic_groups": [
            {
                "name": "B23-DS",
                "event_group_alias": "academic-b23-ds",
                "user_emails": ["student@innopolis.university"],
            }
        ],
    }
    update_response = schedule_client.post("/update-predefined-data", json=payload, headers=parser_headers)
    assert update_response.status_code == 200

    get_response = schedule_client.get("/get-predefined-data", headers=parser_headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["users"][0]["email"] == "student@innopolis.university"
    assert body["academic_groups"][0]["event_group_alias"] == "academic-b23-ds"


def test_update_reports_missing_groups(schedule_client: TestClient, parser_headers: dict[str, str]):
    payload = {
        "users": [{"email": "student@innopolis.university", "groups": ["missing-group"]}],
        "academic_groups": [{"name": "B23-DS", "event_group_alias": "missing-academic", "user_emails": []}],
    }
    response = schedule_client.post("/update-predefined-data", json=payload, headers=parser_headers)
    assert response.status_code == 200
    missing = set(response.json())
    assert "missing-group" in missing
    assert "missing-academic" in missing
