# Alembic

The Schedule environment is based on the [async Alembic configuration with Ruff post-hook](https://gist.github.com/dantetemplar/cbef8b9f1d9d6cde7547629d6d85fcd1).

`schedule` and `schedule_assistant` have independent migration histories. Run commands from the monorepo root with the same `SETTINGS_PATH` as the API (`settings.yaml` by default). Keep existing revision IDs and applied migration files unchanged. See the [shared migration workflow](../../../README.md#database-migrations).

### Apply migrations before the API

Provision the configured PostgreSQL database and user first; Alembic creates tables, not databases.

```bash
uv run -m src.migrations schedule
uv run -m src.migrations schedule_assistant
```

The wrapper applies the existing history with `upgrade head`. Compose runs it in `pre_start`; for local Run/Debug, apply it manually before starting the API. It never creates application objects through `create_all()` or automatically stamps an existing database.

### Create and check revisions

```bash
uv run alembic -c src/schedule/alembic.ini revision --autogenerate -m "describe change"
uv run alembic -c src/schedule/alembic.ini heads
uv run alembic -c src/schedule/alembic.ini check
```

For Schedule Assistant, substitute `src/schedule_assistant/alembic.ini`. Review generated operations, especially renames, defaults, constraints, and data transformations: autogenerate is not a data migration author. Both environments load their models before assigning `target_metadata`; tests exercise their full histories and schema-drift checks. Preserve exactly one head per service.

### Existing databases

A database with an Alembic revision uses the normal `upgrade head` flow. For a nonempty database without history, back it up and compare its schema and data prerequisites against a **specific revision** first. Only after verifying an exact match, record that revision explicitly:

```bash
uv run alembic -c src/schedule/alembic.ini stamp <verified_revision>
uv run -m src.migrations schedule
```

`stamp` changes only version metadata. Never automatically `stamp head`, reset history, or silently accept an unrelated schema. Booking recovery and predefined-file imports remain application operations, not Alembic migrations.

### Rollback

Do not automatically downgrade when rolling back an image. Stop incompatible writers and review whether the database is compatible with the target image. Only run a reviewed, data-preserving downgrade after a backup:

```bash
uv run alembic -c src/schedule/alembic.ini downgrade <reviewed_revision>
```

An irreversible migration must refuse rollback rather than report empty success. Restore a verified backup or implement a forward fix when a lossless downgrade is unavailable.

### Verification

Run each service suite separately against the shared test stack:

```bash
uv run -m pytest tests/schedule/
uv run -m pytest tests/schedule_assistant/
```

Fixtures provision isolated databases, run Alembic to head, and clean application rows without erasing version metadata. Migration tests also cover populated predecessors, repeated upgrades, injected connections, and ORM schema drift.
