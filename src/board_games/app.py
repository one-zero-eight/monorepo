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
    from src.board_games.modules.board_games.photos_repo import photos_repo
    from src.board_games.mongo import document_models
    from src.common_minio import setup_minio
    from src.inh_accounts_sdk import inh_accounts

    await inh_accounts.update_key_set()

    beanie_store = await setup_beanie(settings.mongo.uri, "board_games", document_models)
    minio_store = setup_minio(settings.minio)

    app.state.beanie_store = beanie_store
    app.state.minio_store = minio_store
    photos_repo.post_init(minio_store)

    yield

    await inh_accounts.aclose()
    await beanie_store.close()


app = FastAPI(
    title="Board Games",
    summary="Board games reservations and lending.",
    description="### About this project\n\nAPI for board games catalogue, reservations, and lending.",
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=[],
    servers=[{"url": settings.app_root_path, "description": "Current"}],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
tune_fastapi(app, logger=logger, metrics_namespace="board_games")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import src.board_games.modules.board_games.routes  # noqa: E402
import src.board_games.modules.users.routes  # noqa: E402

app.include_router(src.board_games.modules.users.routes.router)
popule_openapi_tags(app, src.board_games.modules.users.routes)
app.include_router(src.board_games.modules.board_games.routes.router)
popule_openapi_tags(app, src.board_games.modules.board_games.routes)
