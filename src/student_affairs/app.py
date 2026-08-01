__all__ = ["app"]


from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from src.common_fastapi import (
    MIT_LICENSE_INFO,
    ONE_ZERO_EIGHT_CONTACT_INFO,
    popule_openapi_tags,
    tune_fastapi,
)
from src.logging_ import logger

from .config import settings

_OMNIDESK_TIMEOUT_S = 30.0


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.inh_accounts_sdk import inh_accounts

    await inh_accounts.update_key_set()
    app.state.httpx_client = httpx.AsyncClient(timeout=_OMNIDESK_TIMEOUT_S)
    yield
    await inh_accounts.aclose()
    await app.state.httpx_client.aclose()


app = FastAPI(
    title="Student Affairs",
    summary="Student Affairs API",
    description="""
### About this project

This is the API for Student Affairs project developed by one-zero-eight community.
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
tune_fastapi(app, logger=logger, metrics_namespace="student_affairs")


# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


import src.student_affairs.routes  # noqa: E402

# Import routers above and include them below, also populate openapi_tags here if needed
app.include_router(src.student_affairs.routes.router)
popule_openapi_tags(app, src.student_affairs.routes)
# ^
