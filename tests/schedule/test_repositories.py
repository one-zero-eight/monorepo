from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient

from src.schedule.modules.event_groups.repository import event_group_repository
from src.schedule.modules.event_groups.schemas import CreateEventGroup, CreateEventGroupWithoutTags, UpdateEventGroup
from src.schedule.modules.events.repository import SqlEventRepository
from src.schedule.modules.events.schemas import CreateEvent, UpdateEvent
from src.schedule.modules.tags.repository import tag_repository
from src.schedule.modules.tags.schemas import CreateTag, UpdateTag
from src.schedule.storages.sql.models import Base


def test_explicit_associations_match_migrated_schema(schedule_client: TestClient, schedule_portal):
    table_names = {"event_groups_x_tags"}

    def compare_schema(connection):
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_server_default": True,
                "include_object": lambda obj, name, type_, reflected, compare_to: (
                    type_ != "table" or name in table_names
                ),
            },
        )
        assert compare_metadata(context, Base.metadata) == []

    async def check():
        async with schedule_client.app.state.sql_storage.engine.connect() as connection:
            await connection.run_sync(compare_schema)

    schedule_portal.call(check)


def test_group_updates_are_scoped_and_preserve_tags(schedule_client: TestClient, schedule_portal):
    async def check():
        first = await event_group_repository.create(
            CreateEventGroup(
                alias="first-group",
                name="First",
                path="first.ics",
                tags=[CreateTag(alias="course-tag", type="course", name="Course")],
            )
        )
        second = await event_group_repository.create(CreateEventGroup(alias="second-group", name="Second"))
        assert first.id is not None
        assert second.id is not None

        updated = await event_group_repository.update(first.id, UpdateEventGroup(name="Renamed"))
        assert updated.id == first.id
        assert updated.alias == first.alias
        assert updated.name == "Renamed"
        assert [tag.alias for tag in updated.tags] == ["course-tag"]
        unchanged = await event_group_repository.read(second.id)
        assert unchanged is not None
        assert unchanged.name == "Second"
        by_path = await event_group_repository.read_by_path("first.ics")
        assert by_path is not None
        assert by_path.id == first.id
        by_alias = await event_group_repository.read_by_alias(first.alias)
        assert by_alias is not None
        assert by_alias.id == first.id

        batch = await event_group_repository.batch_update(
            {
                first.id: UpdateEventGroup(description="First description"),
                second.id: UpdateEventGroup(name="Second renamed"),
            }
        )
        by_id = {group.id: group for group in batch}
        assert by_id[first.id].name == "Renamed"
        assert by_id[first.id].description == "First description"
        assert [tag.alias for tag in by_id[first.id].tags] == ["course-tag"]
        assert by_id[second.id].name == "Second renamed"
        assert await event_group_repository.batch_update({}) == []
        assert await event_group_repository.read(-1) is None
        assert await event_group_repository.read_by_alias("missing") is None
        assert await event_group_repository.read_by_path("missing.ics") is None

    schedule_portal.call(check)


def test_batch_create_groups(schedule_client: TestClient, schedule_portal):
    async def check():
        groups = await event_group_repository.batch_create(
            [
                CreateEventGroupWithoutTags(alias="batch-first", name="First"),
                CreateEventGroupWithoutTags(alias="batch-second", name="Second"),
            ]
        )
        assert {group.alias for group in groups} == {"batch-first", "batch-second"}
        assert all(group.tags == [] for group in groups)
        assert {group.id for group in await event_group_repository.read_all()} == {group.id for group in groups}
        assert await event_group_repository.batch_create([]) == []

    schedule_portal.call(check)


def test_tag_crud_is_scoped(schedule_client: TestClient, schedule_portal):
    async def check():
        data = CreateTag(alias="first-tag", type="course", name="First")
        first = await tag_repository.create_or_read(data)
        repeated = await tag_repository.create_or_read(data)
        assert repeated.id == first.id
        second = await tag_repository.create_or_read(CreateTag(alias="second-tag", type="course", name="Second"))

        updated = await tag_repository.update(first.id, UpdateTag(name="Renamed"))
        assert updated.id == first.id
        assert updated.alias == first.alias
        assert updated.name == "Renamed"
        assert await tag_repository.update(first.id, UpdateTag()) == updated
        unchanged = await tag_repository.read(second.id)
        assert unchanged is not None
        assert unchanged.name == "Second"
        by_name = await tag_repository.read_by_name("Renamed")
        assert by_name is not None
        assert by_name.id == first.id
        by_alias = await tag_repository.read_by_alias(first.alias)
        assert by_alias is not None
        assert by_alias.id == first.id
        assert {tag.id for tag in await tag_repository.batch_read([first.id, second.id, -1])} == {first.id, second.id}
        assert await tag_repository.batch_read([]) == []
        assert await tag_repository.read_by_name("missing") is None
        assert await tag_repository.read_by_alias("missing") is None

        await tag_repository.delete(first.id)
        assert await tag_repository.read(first.id) is None
        assert [tag.id for tag in await tag_repository.read_all()] == [second.id]

    schedule_portal.call(check)


def test_event_crud_is_scoped(schedule_client: TestClient, schedule_portal):
    async def check():
        repository = SqlEventRepository(schedule_client.app.state.sql_storage)
        first = await repository.create(CreateEvent(name="First", description="Preserve this"))
        second = await repository.create(CreateEvent(name="Second"))
        updated = await repository.update(first.id, UpdateEvent(name="Renamed"))
        assert updated.id == first.id
        assert updated.name == "Renamed"
        assert updated.description == "Preserve this"
        assert updated.patches == []
        read_updated = await repository.read(first.id)
        assert read_updated is not None
        assert read_updated.name == "Renamed"
        unchanged = await repository.read(second.id)
        assert unchanged is not None
        assert unchanged.name == "Second"
        await repository.delete(first.id)
        assert await repository.read(first.id) is None
        remaining = await repository.read(second.id)
        assert remaining is not None
        assert remaining.name == "Second"

    schedule_portal.call(check)
