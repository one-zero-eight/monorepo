__all__ = ["app"]

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from starlette.middleware.cors import CORSMiddleware

from src.common_fastapi import (
    MIT_LICENSE_INFO,
    ONE_ZERO_EIGHT_CONTACT_INFO,
    generate_unique_operation_id,
    tune_fastapi,
)
from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger
from src.timer.config import settings
from src.timer.db.storage import SQLAlchemyStorage
from src.timer.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = SQLAlchemyStorage(settings.db_url.get_secret_value())
    try:
        await inh_accounts.update_key_set()
        async with storage.engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        app.state.sql_storage = storage
        yield
    finally:
        await storage.close_connection()
        await inh_accounts.aclose()


app = FastAPI(
    title="InNoHassle Timer API",
    summary="Timer storage service",
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=[{"name": "Timer", "description": "Timer service"}],
    servers=[{"url": settings.app_root_path, "description": "Current"}],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
tune_fastapi(app, logger=logger, metrics_namespace="timer")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
