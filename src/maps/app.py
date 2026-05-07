__all__ = ["app"]

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from src.fastapi_common import (
    MIT_LICENSE_INFO,
    ONE_ZERO_EIGHT_CONTACT_INFO,
    doc_from_module,
    generate_unique_operation_id,
    tune_fastapi,
)
from src.logging_ import logger

from .config import settings

DESCRIPTION = """
### About this project

This is the API for Maps project in InNoHassle ecosystem developed by one-zero-eight community.

Using this API you can get maps images of Innopolis University and some metadata.

Backend is developed using FastAPI framework on Python.

Note: API is unstable. Endpoints and models may change in the future.

Useful links:
- [Maps API source code](https://github.com/one-zero-eight/maps)
- [InNoHassle Website](https://innohassle.ru/)
"""
TAGS_INFO = []

app = FastAPI(
    title="InNoHassle Maps API",
    summary="View maps of Innopolis University in InNoHassle.",
    description=DESCRIPTION,
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=TAGS_INFO,
    servers=[
        {"url": settings.app_root_path, "description": "Current"},
        {
            "url": "https://api.innohassle.ru/maps/v0",
            "description": "Production environment",
        },
        {
            "url": "https://api.innohassle.ru/maps/staging-v0",
            "description": "Staging environment",
        },
    ],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=None,
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

app.mount(settings.static_mount_path, StaticFiles(directory=settings.static_directory), name="static")

import src.maps.routes  # noqa: E402, I001

# Import routers above and include them below
app.include_router(src.maps.routes.router)
TAGS_INFO.append({"name": "Scenes", "description": doc_from_module(src.maps.routes)})
# ^
