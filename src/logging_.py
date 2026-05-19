"""
Based on https://github.com/dantetemplar/fastapi-how-to-log
"""

__all__ = ["logger"]

import asyncio
import inspect
import logging.config
import os
from typing import Any

import fastapi
from fastapi.dependencies.models import Dependant
from starlette.concurrency import run_in_threadpool


class RelativePathFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.relativePath = os.path.relpath(record.pathname)
        return True


class CleanErrorFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.exc_info:
            if isinstance(record.msg, str):
                record.msg = record.msg.rstrip()
            exc_type, exc, tb = record.exc_info
            top_skip_suffixes = (
                "uvicorn/protocols/http/h11_impl.py",
                "uvicorn/protocols/http/httptools_impl.py",
                "uvicorn/middleware/proxy_headers.py",
                "fastapi/applications.py",
                "starlette/applications.py",
                "starlette/middleware/errors.py",
                "starlette/middleware/cors.py",
                "starlette/middleware/exceptions.py",
                "starlette/_exception_handler.py",
                "fastapi/middleware/asyncexitstack.py",
                "starlette/routing.py",
                "fastapi/routing.py",
                "fastapi/dependencies/utils.py",
                "starlette/concurrency.py",
                "anyio/to_thread.py",
                "anyio/_backends/_asyncio.py",
                "logging_.py",
            )
            tail_cut_suffixes = (
                "httpx/_api.py",
                "starlette/routing.py",
                "fastapi/routing.py",
                "starlette/concurrency.py",
                "anyio/to_thread.py",
                "anyio/_backends/_asyncio.py",
            )

            while tb:
                filename = tb.tb_frame.f_code.co_filename if tb.tb_frame else None
                if filename and filename.endswith(top_skip_suffixes):
                    tb = tb.tb_next
                    continue
                break

            current = tb
            while current and current.tb_next:
                next_filename = current.tb_next.tb_frame.f_code.co_filename if current.tb_next.tb_frame else None
                if next_filename and next_filename.endswith(tail_cut_suffixes):
                    current.tb_next = None
                    break
                current = current.tb_next

            exc.__cause__ = None  # type: ignore
            exc.__context__ = None  # type: ignore
            record.exc_info = (exc_type, exc, tb)  # type: ignore
        return True


dict_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "colorlog.ColoredFormatter",
            "format": "[%(asctime)s] [%(log_color)s%(levelname)s%(reset)s] [%(name)s] %(message)s",
        },
        "src": {
            "()": "colorlog.ColoredFormatter",
            "format": "[%(asctime)s] "
            "[%(log_color)s%(levelname)s%(reset)s] "
            '[%(cyan)sFile "%(relativePath)s", line '
            "%(lineno)d%(reset)s] %(message)s",
        },
    },
    "handlers": {
        "default": {"class": "logging.StreamHandler", "formatter": "default", "stream": "ext://sys.stdout"},
        "src": {"class": "logging.StreamHandler", "formatter": "src", "stream": "ext://sys.stdout"},
    },
    "loggers": {
        "src": {"handlers": ["src"], "level": "INFO", "propagate": False},
        "uvicorn.access": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.error": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "httpx": {"handlers": ["default"], "level": "WARNING", "propagate": False},
    },
}

logging.config.dictConfig(dict_config)

# Copy logger from uvicorn
uvicorn_logger = logging.getLogger("uvicorn")
logging.basicConfig(level=logging.INFO)
logging.getLogger().handlers = uvicorn_logger.handlers

logger = logging.getLogger("src")
logger.addFilter(RelativePathFilter())
logger.addFilter(CleanErrorFilter())

exc_logger = logging.getLogger("uvicorn.error")
exc_logger.addFilter(CleanErrorFilter())


async def run_endpoint_function(*, dependant: Dependant, values: dict[str, Any], is_coroutine: bool) -> Any:
    # Only called by get_request_handler. Has been split into its own function to
    # facilitate profiling endpoints, since inner functions are harder to profile.
    if dependant.call is None:
        raise RuntimeError("dependant.call is None")
    loop = asyncio.get_running_loop()
    start_time = loop.time()
    if is_coroutine:
        r = await dependant.call(**values)
    else:
        r = await run_in_threadpool(dependant.call, **values)
    finish_time = loop.time()
    duration = finish_time - start_time
    callback = dependant.call
    func_name = getattr(callback, "__name__", repr(callback))
    pathname = inspect.getsourcefile(callback) or "unknown"
    lineno = inspect.getsourcelines(callback)[1]
    record = logging.LogRecord(
        name="src.fastapi.run_endpoint_function",
        level=logging.INFO,
        pathname=pathname,
        lineno=lineno,
        msg=f"Handler `{func_name}` took {int(duration * 1000)} ms",
        args=(),
        exc_info=None,
        func=func_name,
    )
    record.relativePath = os.path.relpath(record.pathname)
    logger.handle(record)
    return r


# monkey patch fastapi to log endpoint function duration and link to source code
fastapi.routing.run_endpoint_function = run_endpoint_function  # ty: ignore[invalid-assignment]
