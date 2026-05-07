__all__ = ["lifespan"]

from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Application startup
    yield
