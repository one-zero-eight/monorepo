__all__ = ["app"]

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.common_config import Environment
from src.common_fastapi import generate_unique_operation_id, popule_openapi_tags, tune_fastapi
from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger
from src.schedule import docs
from src.schedule.config import settings
from src.schedule.modules.predefined.storage import JsonPredefinedUsers
from src.schedule.modules.predefined.utils import setup_predefined_data_from_object
from src.schedule.storages.sql import SQLAlchemyStorage


def setup_predefined_data_from_file() -> None:
    from src.schedule.modules.predefined.repository import predefined_repository

    predefined_path = settings.predefined_dir / "innopolis_user_data.json"
    if not predefined_path.exists():
        predefined_json = {"users": [], "academic_groups": []}
    else:
        with predefined_path.open(encoding="utf-8") as predefined_file:
            predefined_json = json.load(predefined_file)

    predefined_storage = JsonPredefinedUsers.from_jsons(predefined_json)
    setup_predefined_data_from_object(predefined_storage)
    _ = predefined_repository


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.schedule.modules.event_groups.repository import event_group_repository
    from src.schedule.modules.tags.repository import tag_repository
    from src.schedule.modules.users.repository import user_repository

    await inh_accounts.update_key_set()

    storage = SQLAlchemyStorage.from_url(settings.db_url.get_secret_value())
    user_repository.update_storage(storage)
    event_group_repository.update_storage(storage)
    tag_repository.update_storage(storage)

    setup_predefined_data_from_file()

    app.state.sql_storage = storage

    yield

    await storage.close_connection()
    await inh_accounts.aclose()


app = FastAPI(
    title=docs.TITLE,
    summary=docs.SUMMARY,
    description=docs.DESCRIPTION,
    version="0.1.0",
    contact=docs.CONTACT_INFO,
    license_info=docs.LICENSE_INFO,
    openapi_tags=docs.TAGS_INFO,
    servers=[
        {"url": settings.app_root_path, "description": "Current"},
        {
            "url": "https://api.innohassle.ru/schedule/v0",
            "description": "Production environment",
        },
        {
            "url": "https://api.innohassle.ru/schedule/staging-v0",
            "description": "Staging environment",
        },
    ],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
tune_fastapi(app, logger=logger, metrics_namespace="schedule")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import src.schedule.modules.event_groups.routes  # noqa: E402
import src.schedule.modules.ics.routes  # noqa: E402
import src.schedule.modules.predefined.routes  # noqa: E402
import src.schedule.modules.tags.routes  # noqa: E402
import src.schedule.modules.users.routes  # noqa: E402

app.include_router(src.schedule.modules.event_groups.routes.router)
popule_openapi_tags(app, src.schedule.modules.event_groups.routes)
app.include_router(src.schedule.modules.ics.routes.router)
popule_openapi_tags(app, src.schedule.modules.ics.routes)
app.include_router(src.schedule.modules.predefined.routes.router)
popule_openapi_tags(app, src.schedule.modules.predefined.routes)
app.include_router(src.schedule.modules.tags.routes.router)
popule_openapi_tags(app, src.schedule.modules.tags.routes)
app.include_router(src.schedule.modules.users.routes.router)
popule_openapi_tags(app, src.schedule.modules.users.routes)

if settings.environment == Environment.DEVELOPMENT:
    import logging

    logger.warning("Enable sqlalchemy logging")
    logging.basicConfig()
    logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
