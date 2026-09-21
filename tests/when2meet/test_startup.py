from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore
from tests.metrics import assert_metrics_contract


def test_when2meet_app_startup(when2meet_client: TestClient):
    response = when2meet_client.get("/openapi.json")
    assert response.status_code == 200
    assert_metrics_contract(when2meet_client, "when2meet")


def test_cleanup_preserves_migration_history(when2meet_client: TestClient):
    app = cast(FastAPI, when2meet_client.app)
    store: BeanieStore = app.state.beanie_store
    portal = when2meet_client.portal
    assert portal is not None

    async def verify_cleanup():
        database = store.client.get_database(store.current_database_name)
        entry = await database.migrations_log.insert_one({"name": "cleanup-test", "is_current": True})
        try:
            history = await database.migrations_log.find({}).to_list()
            await database.cleanup_probe.insert_one({"value": "application data"})

            await store.clear_database()

            assert await database.cleanup_probe.count_documents({}) == 0
            assert await database.migrations_log.find({}).to_list() == history
        finally:
            await database.migrations_log.delete_one({"_id": entry.inserted_id})

    portal.call(verify_cleanup)
