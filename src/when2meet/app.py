__all__ = ["app"]

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

app = FastAPI(
    title="When2Meet API",
    summary="When2Meet service API.",
    description="### About this project\n\nService foundation for When2Meet designed during SWP course.",
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=[],
    servers=[{"url": settings.app_root_path, "description": "Current"}],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=None,
    docs_url="/docs",
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

import src.when2meet.routes  # noqa: E402

app.include_router(src.when2meet.routes.router)
popule_openapi_tags(app, src.when2meet.routes)
