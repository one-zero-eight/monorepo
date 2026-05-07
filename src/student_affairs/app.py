__all__ = ["app"]


from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.fastapi_common import MIT_LICENSE_INFO, ONE_ZERO_EIGHT_CONTACT_INFO, tune_fastapi
from src.logging_ import logger

from .config import settings

DESCRIPTION = """
### About this project

This is the API for Student Affairs project developed by one-zero-eight community.
"""
TAGS_INFO: list[dict] = []


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from src.inh_accounts_sdk import inh_accounts  # noqa: E402

    await inh_accounts.update_key_set()
    yield


app = FastAPI(
    title="Student Affairs",
    summary="Student Affairs API",
    description=DESCRIPTION,
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=TAGS_INFO,
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


import src.student_affairs.routes  # noqa: E402, I001

# Import routers above and include them below
app.include_router(src.student_affairs.routes.router)
# ^
