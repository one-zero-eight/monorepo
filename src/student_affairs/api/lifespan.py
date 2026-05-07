__all__ = ["lifespan"]

from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from src.modules.inh_accounts_sdk import inh_accounts  # noqa: E402

    await inh_accounts.update_key_set()
    yield
