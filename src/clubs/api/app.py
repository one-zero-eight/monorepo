__all__ = ["app"]


from fastapi import FastAPI
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from fastapi_swagger import patch_fastapi
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

import src.logging_  # noqa: F401
from src.api import docs
from src.api.lifespan import lifespan
from src.config import settings
from src.logging_ import logger

# App definition
app = FastAPI(
    title="Clubs",
    summary=docs.SUMMARY,
    description=docs.DESCRIPTION,
    version=docs.VERSION,
    contact=docs.CONTACT_INFO,
    license_info=docs.LICENSE_INFO,
    openapi_tags=docs.TAGS_INFO,
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
app.router.route_class = AutoDeriveResponsesAPIRoute
patch_fastapi(app)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Log validation errors and return human-readable error message.
    Based on https://github.com/dantetemplar/fastapi-how-to-log#exceptions
    """
    as_validation_error = ValidationError.from_exception_data(
        str(request.url.path),
        line_errors=exc.errors(),  # type: ignore
    )
    error_str = str(as_validation_error)
    logger.warning(error_str, exc_info=False)
    return PlainTextResponse(error_str, status_code=422)


@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Log raised HTTPException.
    Based on https://github.com/dantetemplar/fastapi-how-to-log#exceptions
    """
    logger.warning(exc, exc_info=exc)
    return await http_exception_handler(request, exc)


# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.modules.clubs.routes import router as router_clubs  # noqa: E402, I001
from src.modules.users.routes import router as router_users  # noqa: E402, I001
from src.modules.leaders.routes import router as router_leaders  # noqa: E402

# Import routers above and include them below [do not edit this comment]
app.include_router(router_clubs)
app.include_router(router_users)
app.include_router(router_leaders)
# ^
