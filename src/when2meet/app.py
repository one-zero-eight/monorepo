__all__ = ["app"]

from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.common_beanie import setup_beanie
from src.common_fastapi import (
    MIT_LICENSE_INFO,
    ONE_ZERO_EIGHT_CONTACT_INFO,
    generate_unique_operation_id,
    tune_fastapi,
)
from src.logging_ import logger

from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.inh_accounts_sdk import inh_accounts
    from src.when2meet.mongo import document_models

    await inh_accounts.update_key_set()
    beanie_store = await setup_beanie(settings.mongo.uri, settings.service_name, document_models)
    app.state.beanie_store = beanie_store

    yield

    await beanie_store.close()
    await inh_accounts.aclose()


app = FastAPI(
    title="InNoHassle When2Meet API",
    summary="InNoHassle service API.",
    description="### About this project\n\nService foundation for When2Meet designed during SWP course.",
    version="0.2.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=[
        {
            "name": "Meetings",
            "description": "Operations for creating and managing meetings, including tracking participant availability and scheduling time slots.",
        }
    ],
    servers=[{"url": settings.app_root_path, "description": "MVP v0"}],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
    swagger_ui_parameters={"filter": True},
)
tune_fastapi(app, logger=logger, metrics_namespace="when2meet")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import src.when2meet.modules.events.routes  # noqa: E402

app.include_router(src.when2meet.modules.events.routes.router)
