from fastapi.testclient import TestClient

from src.schedule.modules.predefined.repository import predefined_repository
from src.schedule.modules.predefined.storage import JsonPredefinedUsers
from src.schedule.modules.predefined.utils import setup_predefined_data_from_object
from tests.schedule.conftest import create_event_group
from tests.schedule.constants import TEST_USER_EMAIL


def test_get_user_predefined_resolves_group_ids(
    schedule_client: TestClient,
    schedule_portal,
    parser_headers: dict[str, str],
    user_headers: dict[str, str],
):
    group = create_event_group(schedule_client, parser_headers, alias="predefined-target-group")
    me = schedule_client.get("/users/me", headers=user_headers).json()

    predefined = JsonPredefinedUsers(
        users=[JsonPredefinedUsers.InJsonUser(email=TEST_USER_EMAIL, groups=["predefined-target-group"])],
        academic_groups=[],
    )
    setup_predefined_data_from_object(predefined)

    group_ids = schedule_portal.call(predefined_repository.get_user_predefined, me["id"])
    assert group_ids == [group["id"]]
