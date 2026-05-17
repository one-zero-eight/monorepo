__all__ = ["app"]

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.common_beanie import setup_beanie
from src.common_fastapi import (
    MIT_LICENSE_INFO,
    ONE_ZERO_EIGHT_CONTACT_INFO,
    popule_openapi_tags,
    tune_fastapi,
)
from src.logging_ import logger

from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.clubs.modules.clubs.logos_repo import logos_repo
    from src.clubs.mongo import document_models
    from src.common_minio import setup_minio
    from src.inh_accounts_sdk import inh_accounts

    await inh_accounts.update_key_set()

    beanie_store = await setup_beanie(settings.mongo.uri, "clubs", document_models)
    minio_store = setup_minio(settings.minio)

    app.state.beanie_store = beanie_store
    app.state.minio_store = minio_store

    logos_repo.post_init(minio_store)

    yield

    await inh_accounts.aclose()
    await beanie_store.close()


app = FastAPI(
    title="Clubs",
    summary="View the list of clubs and manage the clubs information.",
    description="""
### About this project

This is the API for Clubs project developed by one-zero-eight community.

Using this API you can view active clubs at Innopolis University.
Admins can manage the clubs information.
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
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
tune_fastapi(app, logger=logger)


# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import src.clubs.modules.clubs.routes  # noqa: E402
import src.clubs.modules.leaders.routes  # noqa: E402
import src.clubs.modules.users.routes  # noqa: E402

# Import routers above and include them below, also populate openapi_tags here if needed
app.include_router(src.clubs.modules.users.routes.router)
popule_openapi_tags(app, src.clubs.modules.users.routes)
app.include_router(src.clubs.modules.clubs.routes.router)
popule_openapi_tags(app, src.clubs.modules.clubs.routes)
app.include_router(src.clubs.modules.leaders.routes.router)
popule_openapi_tags(app, src.clubs.modules.leaders.routes)
# ^
