__all__ = [
    "MIT_LICENSE_INFO",
    "ONE_ZERO_EIGHT_CONTACT_INFO",
    "generate_unique_operation_id",
    "popule_openapi_tags",
    "tune_fastapi",
]


import re
from inspect import cleandoc
from logging import Logger
from types import ModuleType

from fastapi import APIRouter, FastAPI
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.requests import Request
from fastapi.routing import APIRoute
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute
from fastapi_swagger import patch_fastapi
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.logging_ import logger


def tune_fastapi(
    app: FastAPI,
    logger: Logger,
    use_auto_derive_route: bool = True,
    use_fastapi_swagger_patch: bool = True,
    use_custom_exception_handlers: bool = True,
) -> None:
    """
    Tune FastAPI with self-hosted Swagger distribution, custom exception handlers and auto derive responses.
    """

    app.state.logger = logger

    if use_auto_derive_route:
        app.router.route_class = AutoDeriveResponsesAPIRoute
    if use_fastapi_swagger_patch:
        patch_fastapi(app)
    if use_custom_exception_handlers:
        register_exception_handlers(app)


def register_exception_handlers(app: FastAPI) -> None:
    app.exception_handler(RequestValidationError)(validation_exception_handler)
    app.exception_handler(StarletteHTTPException)(custom_http_exception_handler)


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
    request.app.state.logger.warning(error_str, exc_info=False)
    return await request_validation_exception_handler(request, exc)


async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    Log raised HTTPException.
    Based on https://github.com/dantetemplar/fastapi-how-to-log#exceptions
    """
    request.app.state.logger.warning(exc, exc_info=exc)
    return await http_exception_handler(request, exc)


def safe_cleandoc(doc: str | None) -> str:
    return cleandoc(doc) if doc else ""


def doc_from_module(module: ModuleType) -> str:
    return safe_cleandoc(module.__doc__)


def generate_unique_operation_id(route: APIRoute) -> str:
    # Better names for operationId in OpenAPI schema.
    # It is needed because clients generate code based on these names.
    # Requires pair (tag name + function name) to be unique.
    # See fastapi.utils:generate_unique_id (default implementation).
    if route.tags:
        operation_id = f"{route.tags[0]}_{route.name}".lower()
    else:
        operation_id = route.name.lower()
    operation_id = re.sub(r"\W+", "_", operation_id)
    return operation_id


ONE_ZERO_EIGHT_CONTACT_INFO = {
    "name": "one-zero-eight (Telegram)",
    "url": "https://t.me/one_zero_eight",
}
MIT_LICENSE_INFO = {
    "name": "MIT License",
    "identifier": "MIT",
}


def popule_openapi_tags(app: FastAPI, router_module: ModuleType) -> None:
    """
    Append to openapi_tags {"name": tag_name, "description": module docstring}
    where tag_name is first tag of router and module docstring is module docstring.
    """
    openapi_tags = app.openapi_tags

    if openapi_tags is None:  # pragma: no cover
        raise ValueError("openapi_tags of app is None")

    if not hasattr(router_module, "router"):  # pragma: no cover
        raise ValueError("router_module has no router variable")

    router: APIRouter = router_module.router

    # check if router has any tags, and get first of them
    if router.tags:
        tag_name = router.tags[0]
    else:
        logger.warning(
            f"router {str(router_module.__name__)} has no tags, so we will not add its documentation to openapi_tags"
        )
        return

    # check if tag name is already in openapi_tags
    if tag_name in openapi_tags:  # pragma: no cover
        raise ValueError(f"tag name {tag_name} is already in openapi_tags")

    # add tag to openapi_tags
    openapi_tags.append(
        {
            "name": tag_name,
            "description": doc_from_module(router_module),
        }
    )
