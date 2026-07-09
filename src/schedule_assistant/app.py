__all__ = ["app"]

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse
from fastapi_swagger import patch_fastapi
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from src.common_fastapi import generate_unique_operation_id, popule_openapi_tags, tune_fastapi
from src.inh_accounts_sdk import inh_accounts
from src.logging_ import logger
from src.schedule_assistant import docs
from src.schedule_assistant.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await inh_accounts.update_key_set()
    yield
    await inh_accounts.aclose()


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
            "url": "https://api.innohassle.ru/schedule-assistant/v0",
            "description": "Production environment",
        },
        {
            "url": "https://api.innohassle.ru/schedule-assistant/staging-v0",
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
tune_fastapi(app, logger=logger)
patch_fastapi(app)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    as_validation_error = ValidationError.from_exception_data(
        str(request.url.path),
        line_errors=exc.errors(),  # type: ignore
    )
    error_str = str(as_validation_error)
    logger.warning(error_str, exc_info=False)
    return PlainTextResponse(error_str, status_code=422)


@app.exception_handler(Exception)
async def parser_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, StarletteHTTPException):
        return await custom_http_exception_handler(request, exc)
    if "/parser/" not in request.url.path:
        logger.exception("Unhandled exception")
    return PlainTextResponse("Internal Server Error", status_code=500)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.warning(exc, exc_info=exc)
    return await http_exception_handler(request, exc)


app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.schedule_assistant.modules.bookings import routes as bookings_routes  # noqa: E402
from src.schedule_assistant.modules.issues import routes as issues_routes  # noqa: E402
from src.schedule_assistant.modules.parser import routes as parser_routes  # noqa: E402
from src.schedule_assistant.modules.schedule import routes as schedule_routes  # noqa: E402
from src.schedule_assistant.modules.schedule_config import routes as schedule_config_routes  # noqa: E402

app.include_router(bookings_routes.router)
popule_openapi_tags(app, bookings_routes)
app.include_router(issues_routes.router)
popule_openapi_tags(app, issues_routes)
app.include_router(parser_routes.router)
popule_openapi_tags(app, parser_routes)
app.include_router(schedule_routes.router)
popule_openapi_tags(app, schedule_routes)
app.include_router(schedule_config_routes.router)
popule_openapi_tags(app, schedule_config_routes)
