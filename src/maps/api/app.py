__all__ = ["app"]

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi_swagger import patch_fastapi
from starlette.middleware.cors import CORSMiddleware

import src.api.logging_  # noqa: F401
from src.api import docs
from src.api.lifespan import lifespan
from src.config import settings

# App definition
app = FastAPI(
    title=docs.TITLE,
    summary=docs.SUMMARY,
    description=docs.DESCRIPTION,
    version=docs.VERSION,
    contact=docs.CONTACT_INFO,
    license_info=docs.LICENSE_INFO,
    openapi_tags=docs.TAGS_INFO,
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
    generate_unique_id_function=docs.generate_unique_operation_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)

patch_fastapi(app)

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(settings.static_mount_path, StaticFiles(directory=settings.static_directory), name="static")

from src.modules.scenes.routes import router as router_bookings  # noqa: E402

app.include_router(router_bookings)
