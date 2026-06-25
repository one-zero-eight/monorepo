# Creating a new service

Each service is a standalone FastAPI app under `src/<service_name>/`, run with `uv run -m src.<service_name>`. Pick a layout tier by complexity and copy the closest reference then trim what you do not need.

Tiers:
- **Very simple** — (for example, student_affairs service): `app.py` + `routes.py`, handlers only, optional Accounts lifespan.
- **Simple** — (for example, maps service): above + `*_repo.py`, `schemas.py`, optional static mount.
- **Normal** — (for example, clubs service): `modules/<area>/`, `dependencies.py`, `mongo.py`, Beanie + MinIO lifespan.

Replace `my_service` / `MyService` in the examples below with your service name.

---

## Shared files (every tier)

### `src/my_service/__init__.py`

Leave empty.

### `src/my_service/__main__.py`

```python
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

os.chdir(BASE_DIR)

import uvicorn  # noqa: E402

args = sys.argv[1:]
extended_args = [
    "src.my_service.app:app",
    "--use-colors",
    "--proxy-headers",
    "--forwarded-allow-ips=*",
    "--port=8020",  # pick a port not used by other src/*/__main__.py
    *args,
]

print(f"🚀 Starting Uvicorn server: 'uvicorn {' '.join(extended_args)}'")
uvicorn.main.main(extended_args)
```

### `src/my_service/config_schema.py`

Add only what the service needs. Register `my_service_service: MyServiceSettings | None = None` in `config_root_schema.py` and load it with `require_not_none` in `config.py` (service settings are always required in `settings.yaml`).

```python
from pathlib import Path

from pydantic import Field

from src.common_config import MinioSettings, MongoDatabaseSettings, ServiceSettingsBase


class MyServiceSettings(ServiceSettingsBase):
    greeting: str = "hello"
    mongo: MongoDatabaseSettings = Field(default_factory=MongoDatabaseSettings)
    minio: MinioSettings = Field(default_factory=MinioSettings)
    static_mount_path: str = "/static"
    static_directory: Path = Path("src/my_service/static")
```

### `src/my_service/config.py`

```python
from src.config_root_schema import load_root_settings, require_not_none
from src.my_service.config_schema import MyServiceSettings

root_settings = load_root_settings()
settings: MyServiceSettings = require_not_none(
    root_settings.my_service_service,
    "My service settings are not configured, please check your settings file",
)
```

### `src/my_service/app.py`

Same file for every tier. Drop unused lifespan steps, imports, `StaticFiles` mount, and extra router blocks when the service does not need them.

```python
__all__ = ["app"]

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from src.common_beanie import setup_beanie
from src.common_fastapi import (
    MIT_LICENSE_INFO,
    ONE_ZERO_EIGHT_CONTACT_INFO,
    generate_unique_operation_id,
    popule_openapi_tags,
    tune_fastapi,
)
from src.common_minio import setup_minio
from src.logging_ import logger

from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.inh_accounts_sdk import inh_accounts
    from src.my_service.modules.items.files_repo import files_repo
    from src.my_service.mongo import document_models

    await inh_accounts.update_key_set()

    beanie_store = await setup_beanie(settings.mongo.uri, "my_service", document_models)
    minio_store = setup_minio(settings.minio)

    app.state.beanie_store = beanie_store
    app.state.minio_store = minio_store

    files_repo.post_init(minio_store)

    yield

    await beanie_store.close()


app = FastAPI(
    title="My Service",
    summary="My Service API",
    description="### About this project\n\nShort description.",
    version="0.1.0",
    contact=ONE_ZERO_EIGHT_CONTACT_INFO,
    license_info=MIT_LICENSE_INFO,
    openapi_tags=[],
    servers=[{"url": settings.app_root_path, "description": "Current"}],
    root_path=settings.app_root_path,
    root_path_in_servers=False,
    generate_unique_id_function=generate_unique_operation_id,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    swagger_ui_oauth2_redirect_url=None,
)
tune_fastapi(app, logger=logger)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(settings.static_mount_path, StaticFiles(directory=settings.static_directory), name="static")

import src.my_service.routes  # noqa: E402
import src.my_service.modules.items.routes  # noqa: E402

app.include_router(src.my_service.routes.router)
popule_openapi_tags(app, src.my_service.routes)
app.include_router(src.my_service.modules.items.routes.router)
popule_openapi_tags(app, src.my_service.modules.items.routes)
```

### `routes.py`

```python
from fastapi import APIRouter
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.dependencies import INH_TOKEN_AUTH

router = APIRouter(tags=["MyService"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/hello")
async def hello(auth: INH_TOKEN_AUTH) -> dict[str, str]:
    return {"message": f"hello, {auth.email}"}
```


### `tests/my_service/conftest.py`

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def my_service_client() -> Iterator[TestClient]:
    from src.my_service import app as my_service_app

    with TestClient(my_service_app.app) as client:
        yield client
```

### `tests/my_service/test_my_service_startup.py`

```python
from fastapi.testclient import TestClient


def test_my_service_app_startup(my_service_client: TestClient):
    response = my_service_client.get("/openapi.json")
    assert response.status_code == 200
```

---

## Tier 2 — Simple

Extra files on top of the shared layout.

### `src/my_service/schemas.py`

```python
from src.common_config import BaseSchema


class Item(BaseSchema):
    id: str
    title: str
```

### `src/my_service/my_service_repo.py`

```python
from pathlib import Path

import yaml

from .schemas import Item

data_path = Path(__file__).resolve().parent / "items.yaml"


def load_items(path: Path) -> list[Item]:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return [Item.model_validate(row) for row in raw.get("items", [])]


items = load_items(data_path)


def get_all_items() -> list[Item]:
    return items


def find_by_id(item_id: str) -> Item | None:
    return next((item for item in items if item.id == item_id), None)
```

### `src/my_service/routes.py` (thin handlers)

```python
from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from . import my_service_repo
from .schemas import Item

router = APIRouter(tags=["Items"], route_class=AutoDeriveResponsesAPIRoute)


@router.get("/items/")
def list_items() -> list[Item]:
    return my_service_repo.get_all_items()


@router.get("/items/{item_id}")
def get_item(item_id: str) -> Item:
    item = my_service_repo.find_by_id(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

---

## Tier 3 — Normal

### `src/my_service/mongo.py`

```python
__all__ = ["Item", "ItemSchema", "document_models"]

from typing import ClassVar

from pymongo import IndexModel

from src.common_beanie import BeanieDocument
from src.common_pydantic import BaseSchema


class ItemSchema(BaseSchema):
    slug: str
    title: str


class Item(ItemSchema, BeanieDocument):
    class Settings(BeanieDocument.Settings):
        indexes: ClassVar = [IndexModel("slug", unique=True)]


document_models = [Item]
```

### `src/my_service/dependencies.py`

```python
from typing import Annotated

from fastapi import Depends, HTTPException

from src.dependencies import INH_TOKEN_AUTH


async def ensure_admin(auth: INH_TOKEN_AUTH):
    # load role from DB, external API, etc.
    if auth.email != "admin@innopolis.university":
        raise HTTPException(status_code=403, detail="Admin only")
    return auth


MY_SERVICE_ADMIN_AUTH = Annotated[object, Depends(ensure_admin)]
```

### `src/my_service/modules/items/routes.py`

```python
from beanie import PydanticObjectId
from fastapi import APIRouter, HTTPException
from fastapi_derive_responses import AutoDeriveResponsesAPIRoute

from src.my_service.dependencies import MY_SERVICE_ADMIN_AUTH
from src.my_service.mongo import Item

from . import items_repo

router = APIRouter(
    prefix="/items",
    tags=["Items"],
    route_class=AutoDeriveResponsesAPIRoute,
)


@router.get("/")
async def list_items() -> list[Item]:
    return await items_repo.read_all()


@router.post("/")
async def create_item(body: items_repo.CreateItem, _: MY_SERVICE_ADMIN_AUTH) -> Item:
    return await items_repo.create(body)


@router.get("/{id}")
async def get_item(id: PydanticObjectId) -> Item:
    item = await items_repo.read(id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```

### `src/my_service/modules/items/items_repo.py`

```python
from beanie import PydanticObjectId

from src.my_service.mongo import Item, ItemSchema


class CreateItem(ItemSchema):
    pass


async def create(data: CreateItem) -> Item:
    return await Item.model_validate(data, from_attributes=True).create()


async def read(id: PydanticObjectId) -> Item | None:
    return await Item.get(id)


async def read_all() -> list[Item]:
    return await Item.all().to_list()
```

### `src/my_service/modules/items/files_repo.py`

```python
__all__ = ["files_repo"]

from src.common_minio import MinioStore


class FilesRepo:
    def __init__(self) -> None:
        self._minio_store: MinioStore | None = None

    def post_init(self, minio_store: MinioStore) -> None:
        self._minio_store = minio_store

    @property
    def minio_store(self) -> MinioStore:
        if self._minio_store is None:  # pragma: no cover
            raise RuntimeError("FilesRepo.post_init was not called from app lifespan")
        return self._minio_store


files_repo = FilesRepo()
```

### `tests/my_service/conftest.py` (tier 3 — DB/MinIO isolation)

```python
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.common_beanie import BeanieStore
from src.common_minio import MinioStore


@pytest.fixture(scope="session")
def my_service_client(request: pytest.FixtureRequest):
    request.getfixturevalue("mock_inh_accounts_http")
    from src.my_service import app as my_service_module

    with TestClient(my_service_module.app) as client:
        yield client


@pytest.fixture(autouse=True)
def clean_up_stores_per_test(request: pytest.FixtureRequest):
    if "my_service_client" not in request.fixturenames:
        yield
        return

    client: TestClient = request.getfixturevalue("my_service_client")
    portal = client.portal
    assert portal is not None

    app = cast(FastAPI, client.app)
    beanie_store: BeanieStore = app.state.beanie_store
    minio_store: MinioStore = app.state.minio_store

    portal.call(beanie_store.clear_database)
    minio_store.clear_bucket()

    yield
```

---

## Monorepo wiring

### `src/config_root_schema.py` (add service field)

```python
from src.my_service.config_schema import MyServiceSettings


class Settings(BaseSchema):
    # ...
    my_service_service: MyServiceSettings | None = None
```

Regenerate YAML schema:

```bash
uv run python scripts/generate_settings_schema.py
```

### `settings.yaml` (local)

```yaml
my_service_service:
  environment: development
  app_root_path: ""
  cors_allow_origin_regex: ".*"
  greeting: hello
```

### `tests/conftest_runtime_settings.py` (pytest override)

```python
from src.my_service.config_schema import MyServiceSettings


def load_root_settings() -> Settings:
    return Settings(
        # ...
        my_service_service=MyServiceSettings(
            environment=Environment.TESTING,
            mongo=MongoDatabaseSettings(uri=SecretStr(mongo_uri.replace("<service_name>", "my_service"))),
            minio=MinioSettings(
                endpoint=SUITE_MINIO_ENDPOINT,
                access_key=SUITE_MINIO_ACCESS_KEY,
                secret_key=SecretStr(SUITE_MINIO_SECRET_KEY),
                bucket=minio_bucket.replace("<service_name>", "my_service"),
            ),
        ),
    )
```

### `pyproject.toml` (optional dependency group)

```toml
[dependency-groups]
my-service = [
    "some-package>=1.0.0",
]
```

### `docker-compose.yaml`

Add a service block so the API runs with the rest of the dev stack (`docker compose up --build --wait`). The image is built from `api.Dockerfile`; the container always listens on port `8000` (gunicorn), so map the **host** port to `8000` — use the same host port as in `src/my_service/__main__.py` (existing services: maps `8009`, clubs `8014`, student-affairs `8015`).

```yaml
  my-service:
    build:
      context: .
      dockerfile: api.Dockerfile
      args:
        APP_MODULE: src.my_service.app:app
    restart: no
    ports:
      - "8020:8000"  # host port from __main__.py → container 8000
    volumes:
      - "./settings.yaml:/app/settings.yaml:ro"
    deploy:
      resources:
        limits:
          memory: 1g
        reservations:
          memory: 500m
    depends_on:  # omit if the service does not use Mongo/MinIO
      mongodb:
        condition: service_healthy
      minio:
        condition: service_started
```

- **`APP_MODULE`** must point at `src.<package>.app:app` (the FastAPI instance in `app.py`).
- **`settings.yaml`** is mounted read-only; ensure `my_service_service` is configured there with correct `mongo` / `minio` endpoints (`mongodb:27017`, `minio:9000` when talking to the compose network, not `localhost`).

`docker-compose.test.yaml` only runs shared test infra (Mongo/MinIO via lazytainer); API services are not added there — tests use `TestClient` and fixtures from [TESTING.md](./TESTING.md).

### `.vscode/launch.json`

Add new launch configuration for VSCode:

```json
{
  "version": "0.2.0",
  "configurations": [
     ...
    {
      "name": "my service",
      "type": "debugpy",
      "request": "launch",
      "module": "src.my_service",
      "args": ["--reload"],
      "cwd": "${workspaceFolder}",
      "console": "integratedTerminal"
    },
    ...
  ]
}
```

### `.idea/runConfigurations/my_service.xml`

Add new run configuration for PyCharm:

```xml
<component name="ProjectRunConfigurationManager">
  <configuration default="false" name="my service" type="PythonConfigurationType" factoryName="Python">
    <option name="SCRIPT_NAME" value="src.my_service" />
    <module name="monorepo" />
    <option name="ENV_FILES" value="" />
    <option name="INTERPRETER_OPTIONS" value="" />
    <option name="PARENT_ENVS" value="true" />
    <envs>
      <env name="PYTHONUNBUFFERED" value="1" />
    </envs>
    <option name="SDK_HOME" value="" />
    <option name="WORKING_DIRECTORY" value="$PROJECT_DIR$" />
    <option name="IS_MODULE_SDK" value="true" />
    <option name="ADD_CONTENT_ROOTS" value="true" />
    <option name="ADD_SOURCE_ROOTS" value="true" />
    <EXTENSION ID="PythonCoverageRunConfigurationExtension" runner="coverage.py" />
    <option name="RUN_TOOL" value="true" />
    <option name="PARAMETERS" value="--reload" />
    <option name="SHOW_COMMAND_LINE" value="false" />
    <option name="EMULATE_TERMINAL" value="false" />
    <option name="MODULE_MODE" value="true" />
    <option name="REDIRECT_INPUT" value="false" />
    <option name="INPUT_FILE" value="" />
    <method v="2" />
  </configuration>
</component>
```

---

## Testing

See [TESTING.md](./TESTING.md). Do not start Docker from tests — run `docker compose -f docker-compose.test.yaml up --wait` before pytest when the service uses Mongo or MinIO.

---

## Run

```bash
cp settings.example.yaml settings.yaml   # once
uv run -m src.my_service --reload
uv run -m pytest tests/my_service/
```
