Be concise. Avoid overly long explanations. Provide direct answers, or apply code solutions with minimal extra commentary. Only include clarifications if explicitly requested or really necessary, to reduce token usage and keep responses focused. Don't ask for unecessary permission, just go.

### Code

If you need to scaffold a new service, use the [NEW_SERVICE.md](NEW_SERVICE.md) guide.

DO NOT CREATE useless md files such as QUICKSTART, TASK and so on.
DO NOT MAKE ridiculous fallbacks.
DO NOT MAKE any backward compatibility shit unless requested.
DO NOT EVER WRITE "try: import ... except", as all libraries are expected to be installed.
DO NOT WRITE "from __future__ import annotations", as Python 3.14+ uses deferred annotations by default.
DO NOT USE response_model= in route decorator, use type hints instead:

    ```python
    # Good.
    @router.get("/scenes/")
    async def scenes() -> list[Scene]:
        return await repo.get_all_scenes()


    # Bad.
    @router.get("/scenes/", response_model=list[Scene])
    async def scenes():
        return await repo.get_all_scenes()
    ```

**FastAPI Depends** — declare reusable deps as `XxxDep = Annotated[T, Depends(factory)]` (PascalCase + `Dep` suffix). Use the alias as the parameter type; do not write `Depends(...)` in route signatures. Name route params after the value (`users`, `session`), or `_` when the dep is auth-only:

```python
# dependencies.py
def get_user_repository(session: SessionDep) -> SqlUserRepository:
    return SqlUserRepository(session)

UserRepoDep = Annotated[SqlUserRepository, Depends(get_user_repository)]
CurrentUserIdDep = Annotated[int, Depends(get_current_user_id)]

# route
@router.get("/me")
async def get_me(user_id: CurrentUserIdDep, users: UserRepoDep) -> ViewUser:
    ...
```

### Models vs schemas

- **model** — SQLAlchemy ORM mapped to a table (`src/<service>/models.py`). Persist/query via the session; not an API contract.
- **schema** — Pydantic (or similar) request/response/DTO types (`modules/*/schemas.py`, and service-level `config_schema.py` / `schema_base.py` for settings). Wire these in routes and OpenAPI; do not put ORM models in route signatures.

Do not name API DTOs `*Model` or ORM tables `*Schema`.

### Router documentation

Use the router module's docstring to document shared behavior, business rules, and workflows in detail when needed; keep endpoint-specific details in endpoint docstrings. This module docstring is published as the description of the router's first OpenAPI tag through `popule_openapi_tags(app, router_module)` (e.g. `popule_openapi_tags(app, src.schedule.modules.users.routes)`). Register this call after `app.include_router(...)` when wiring a router whose module documentation should appear in OpenAPI.

### SQLAlchemy

Used in `schedule` (async) and `schedule_assistant` (sync). Prefer SQLAlchemy 2.0 style.

Layout: `src/<service>/storage.py` (engine / sessionmaker), `src/<service>/models.py` (ORM), `src/<service>/dependencies.py` (`get_session`, `SessionDep`, `*RepoDep`, auth deps).

**Models** — declarative classes with `Mapped[...]` + `mapped_column` / `relationship` (not classic `Column(...)` without annotations):

```python
class User(Base, IdMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    favorites: Mapped[list[Favorite]] = relationship(...)
```

**Queries** — use model columns in `select` / `where` / `order_by` / `join` / `index_elements` (`User.email`, `EventGroup.alias`), not string names (`"email"`, `["alias"]`):

```python
select(User).where(User.email == email)
insert(...).on_conflict_do_update(index_elements=[EventGroup.alias], ...)
```

`.values(**model_dump(...))` and executemany `params=[{...}, ...]` still use string keys — that is fine; batch UPDATE dicts cannot take Column objects. Avoid raw `text()` in app code except when there is no ORM/Core equivalent.

**Sessions (FastAPI)** — one session per request via `Depends`, not per-method `create_session()` and not `async_scoped_session` / ContextVar globals. `schedule` uses async `AsyncSession`; `schedule_assistant` uses sync `Session` the same way:

```python
# dependencies.py
def get_session(request: Request) -> Generator[Session]:  # or AsyncIterator[AsyncSession]
    session = request.app.state.sessionmaker()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

SessionDep = Annotated[Session, Depends(get_session)]

def get_schedule_config_repository(session: SessionDep) -> ScheduleConfigRepository:
    return ScheduleConfigRepository(session)

ScheduleConfigRepoDep = Annotated[ScheduleConfigRepository, Depends(get_schedule_config_repository)]

# route
@router.get("/")
async def get_config(config_repo: ScheduleConfigRepoDep) -> ScheduleConfig:
    ...
```

Repos do not commit; the request-scoped session commits once at the end. Outside HTTP (tests, scripts, background tasks), open a session from `storage.open_session()` / `sessionmaker()` and pass it into the repository.

### Migrations

- Use versioned Beanie/Alembic migrations for stored schema/data changes, not runtime legacy compatibility. See [database migration workflow](DATABASE.md#migrations).
- Keep published revisions, frozen historical models, and existing migration histories intact; do not rewrite history or blindly stamp databases to head.
- Run migrations before API startup through Compose `pre_start` or locally with `uv run -m src.migrations <service>`, never from workers or app lifespan. Provision the target database first and serialize migrations against it.
- Beanie records history after the data transaction commits: migrations must be idempotent and preserve unrelated fields, IDs, and existing timestamps.
- Test upgrades from both an empty database and populated previous revisions using shared test infrastructure.

### Git

When finishing a task with code changes:
- stage only the relevant changes (not the full working tree / unrelated diffs); do not stage secrets (`.env`, credentials, local `settings.yaml`)
- draft a concise Conventional Commit message using the examples below as a reference; describe the purpose or behavioral change, not just the files edited. **Always include a scope:**
  - service/area scope when the change is local (e.g. `feat(maps): …`, `fix(schedule): …`)
  - comma-separated scopes when a few services are touched (e.g. `chore(schedule, maps): …`)
  - `general` for repo-wide / all-services changes (e.g. `chore(general): …`, `docs(general): …`)
- **Base the message on the full staged diff** (`git diff --cached` / all files being committed), not only the last edit in the chat. One commit = one message that covers the whole staged set.
- if the change is tied to a GitHub issue, put a trailer in the commit body: `Closes one-zero-eight/monorepo#123` when the commit closes the issue, or `Relates one-zero-eight/monorepo#123` when it only relates to it
- do **not** run `git commit` unless the user explicitly asks

Good examples from this repository's history (a subject alone is enough for simple changes):
- `feat(when2meet): support independent booking titles`
- `fix(room-booking): restore calendar and free-busy booking matching`
- `fix(room-booking, schedule-assistant): preserve booking intents and verify Outlook outcomes`
- `docs(general): start PostgreSQL with development infrastructure`
- `feat(general): gate API startup on database migrations\n\nRelates one-zero-eight/monorepo#249`


### Testing

Follow the repository testing guidelines in [TESTING.md](TESTING.md).

Run pytest from the repository root: `uv run -m pytest` for all tests, or select relevant suites (e.g. `uv run -m pytest tests/clubs/ tests/events/`). Multiple services can run in one process. Shared MongoDB fields/settings belong in the non-Document `BeanieDocumentMixin`; concrete models inherit from it and `Document` directly to avoid shared Beanie initialization state.

`prek` checks can modify files through fixers and formatters. Review the existing diff before running them and the resulting diff afterward; preserve unrelated changes.

! Assume that the test infrastructure is already running by developer (using `docker compose -f docker-compose.test.yaml up --wait`).

When writing tests:
- prefer behavior and contract tests over implementation-detail tests
- use shared test infrastructure
- mock only external systems
- keep tests independent and parallel-safe
- run the relevant pytest command before claiming the change is complete
