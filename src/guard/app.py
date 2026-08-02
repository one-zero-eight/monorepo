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
    from src.guard.mongo import document_models
    from src.inh_accounts_sdk import inh_accounts

    await inh_accounts.update_key_set()

    beanie_store = await setup_beanie(settings.mongo.uri, "guard", document_models)
    app.state.beanie_store = beanie_store

    yield

    await inh_accounts.aclose()
    await beanie_store.close()


app = FastAPI(
    title="InNoHassle Guard API",
    summary="Add users to Google Spreadsheets only after InNoHassle Accounts authentication.",
    description="""
### About this project

This is the API for Guard project in InNoHassle ecosystem developed by [one-zero-eight](https://t.me/one_zero_eight) community.

Guard gates access to Google Spreadsheets by requiring users to authenticate via InNoHassle Accounts. Only authenticated users are added to spreadsheets with configured permissions (writer/reader). This ensures that only verified Innopolis University community members can access shared documents.

Backend is developed using FastAPI framework on Python.

Note: API is unstable. Endpoints and models may change in the future.

Useful links:
- [Guard API source code](https://github.com/one-zero-eight/guard)
- [InNoHassle Website](https://innohassle.ru)
""",
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=[],
    servers=[
        {"url": settings.app_root_path, "description": "Current"},
        {
            "url": "https://api.innohassle.ru/guard/v0",
            "description": "Production environment",
        },
        {
            "url": "https://api.innohassle.ru/guard/staging-v0",
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
tune_fastapi(app, logger=logger, metrics_namespace="guard")


# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import src.guard.modules.google_.routes  # noqa: E402

# Import routers above and include them below, also populate openapi_tags here if needed
app.include_router(src.guard.modules.google_.routes.router)
popule_openapi_tags(app, src.guard.modules.google_.routes)
# ^
