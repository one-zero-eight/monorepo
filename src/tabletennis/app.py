__all__ = ["app"]

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

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
    from src.inh_accounts_sdk import inh_accounts

    await inh_accounts.update_key_set()
    yield
    await inh_accounts.aclose()


app = FastAPI(
    title="InNoHassle Table Tennis API",
    summary="Table tennis leaderboard and queue in InNoHassle.",
    description="### About this project\n\nAPI for managing table tennis players and games.",
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    servers=[
        {"url": settings.app_root_path, "description": "Current"},
    ],
    openapi_tags=[],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
tune_fastapi(app, logger=logger)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import src.tabletennis.routes  # noqa: E402

app.include_router(src.tabletennis.routes.router)
popule_openapi_tags(app, src.tabletennis.routes)
