__all__ = ["app"]

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.common_beanie import setup_beanie
from src.common_fastapi import (
    MIT_LICENSE_INFO,
    ONE_ZERO_EIGHT_CONTACT_INFO,
    generate_unique_operation_id,
    popule_openapi_tags,
    tune_fastapi,
)
from src.logging_ import logger

from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.common_minio import setup_minio
    from src.events.images_repo import images_repo
    from src.events.mongo import document_models
    from src.inh_accounts_sdk import inh_accounts

    await inh_accounts.update_key_set()

    beanie_store = await setup_beanie(settings.mongo.uri, "events", document_models)
    minio_store = setup_minio(settings.minio)

    app.state.beanie_store = beanie_store
    app.state.minio_store = minio_store

    images_repo.post_init(minio_store)

    yield

    await inh_accounts.aclose()
    await beanie_store.close()


app = FastAPI(
    title="Events",
    summary="Create, manage, and enroll in events.",
    description="""
### About this project

This is the API for the Events project developed by one-zero-eight community.

Club leaders and event managers create event drafts, moderators review and
publish them, and any authenticated user can view published events and enroll.
""",
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=[],
    servers=[
        {"url": settings.app_root_path, "description": "Current"},
    ],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
tune_fastapi(app, logger=logger, metrics_namespace="events")

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import src.events.modules.drafts.routes  # noqa: E402
import src.events.modules.events.routes  # noqa: E402
import src.events.modules.locales.routes  # noqa: E402
import src.events.modules.submissions.routes  # noqa: E402
import src.events.modules.users.routes  # noqa: E402

app.include_router(src.events.modules.drafts.routes.router)
popule_openapi_tags(app, src.events.modules.drafts.routes)
app.include_router(src.events.modules.submissions.routes.router)
popule_openapi_tags(app, src.events.modules.submissions.routes)
app.include_router(src.events.modules.events.routes.router)
popule_openapi_tags(app, src.events.modules.events.routes)
app.include_router(src.events.modules.users.routes.router)
popule_openapi_tags(app, src.events.modules.users.routes)
app.include_router(src.events.modules.locales.routes.router)
popule_openapi_tags(app, src.events.modules.locales.routes)
