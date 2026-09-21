# Databases

Run commands from the repository root. Connection settings come from `settings.yaml` or the service's defaults. When omitted, the MongoDB URI and MinIO endpoint use `mongodb:27017` and `minio:9000` inside Docker, or `127.0.0.1:27017` and `127.0.0.1:9000` outside Docker. PostgreSQL defaults to `postgres:5432` inside Docker or `127.0.0.1:5432` outside Docker, with user/password `postgres` and separate databases named `schedule` and `schedule_assistant`. Explicit connection settings override these local-development defaults; databases must still be created before running migrations.

## Migrations

Apply pending migrations before starting a database-backed service:

```bash
uv run -m src.migrations clubs && uv run -m src.clubs --reload
```

Supported services: `board_games`, `clubs`, `events`, `forms`, `guard`, `tabletennis`, `when2meet`, `schedule`, and `schedule_assistant`. Use Python package names, not Compose names such as `board-games`. No migrations are needed for `maps`, `room_booking`, or `student_affairs`.

After pulling new migrations, stop the API, apply them, then restart it; `--reload` does not run migrations. The shared CLI applies forward migrations only. Review generated revisions, keep published revisions unchanged, and write idempotent migrations.

### MongoDB (Beanie)

See the [official Beanie migrations documentation](https://beanie-odm.dev/tutorial/migrations/) for writing and running migrations.

Create a revision in the service's migrations directory:

```bash
uv run beanie new-migration -n describe_change -p src/clubs/migrations
```

Keep the generated timestamp in the filename; filenames beginning with `_` are skipped by Beanie.

MongoDB migrations require a replica set; local Compose and CI configure authenticated `rs0` automatically. Custom local MongoDB URIs should include `directConnection=true&replicaSet=rs0`. Preserve existing data and config volumes. Converting an existing standalone server requires a backed-up upgrade procedure, not deleting volumes.

Beanie runs migrations in transactions, but records history after the transaction commits. A migration can therefore run again after a crash; make data changes idempotent. Handle index changes explicitly rather than relying on data-transaction rollback.

### PostgreSQL (Alembic)

See the [official Alembic documentation](https://alembic.sqlalchemy.org/en/latest/tutorial.html) for creating and running migrations.

`schedule` and `schedule_assistant` have independent migration histories. Provision the configured PostgreSQL databases and users first; Alembic creates tables, not databases.

```bash
uv run -m src.migrations schedule
uv run -m src.migrations schedule_assistant
```

The shared CLI runs `upgrade head`; it does not create application objects through `create_all()` or automatically stamp an existing database.

#### Create and check revisions

```bash
uv run alembic -c src/schedule/alembic.ini revision --autogenerate -m "describe change"
uv run alembic -c src/schedule/alembic.ini heads
uv run alembic -c src/schedule/alembic.ini check
```

For Schedule Assistant, substitute `src/schedule_assistant/alembic.ini`. Review generated operations, especially renames, defaults, constraints, and data transformations: autogenerate does not write data migrations. Preserve exactly one head per service.

The Schedule environment is based on the [async Alembic configuration with Ruff post-hook](https://gist.github.com/dantetemplar/cbef8b9f1d9d6cde7547629d6d85fcd1).

#### Existing databases

A database with an Alembic revision uses the normal upgrade flow. For a nonempty database without history, back it up and compare its schema and data prerequisites against a **specific revision** first. Only after verifying an exact match, record that revision explicitly:

```bash
uv run alembic -c src/schedule/alembic.ini stamp <verified_revision>
uv run -m src.migrations schedule
```

`stamp` changes only version metadata. Never blindly `stamp head`, reset history, or accept an unrelated schema. Booking recovery and predefined-file imports remain application operations, not Alembic migrations.

#### Rollback

Do not automatically downgrade when rolling back an image. Stop incompatible writers and check database compatibility with the target image. Only run a reviewed, data-preserving downgrade after a backup:

```bash
uv run alembic -c src/schedule/alembic.ini downgrade <reviewed_revision>
```

Irreversible migrations must refuse rollback. Restore a verified backup or implement a forward fix when a lossless downgrade is unavailable.

### Deployment

Use Docker Compose **5.3.0+**. Database-backed APIs run migrations through `pre_start` hooks on container creation/recreation; failures block startup. `docker compose restart` does not run these hooks.

Back up data before migrations, stop incompatible writers, and do not run migrations concurrently against the same database. Hooks do not serialize deployments or make a multi-service rollout atomic.

### Verification

Run service suites separately against the shared test stack:

```bash
uv run -m pytest tests/schedule/
uv run -m pytest tests/schedule_assistant/
```

See [TESTING.md](TESTING.md) for infrastructure setup and service test commands.

## Dump and restore

These examples target local Compose databases. Replace `clubs` or `schedule` with the database name from your service settings. Stop application writers for a consistent MongoDB dump, and stop the target service before restoring. Restore commands below replace existing data; check the target first. Apply pending migrations before restarting the API.

### MongoDB

Requires `mongodb` running (`docker compose up --wait mongodb`).

Dump:

```bash
docker compose exec mongodb sh -c 'mongodump --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db clubs --out /dump'
docker compose cp mongodb:/dump/clubs ./clubs_dump
```

Restore (copy the dump into the container first):

```bash
docker compose cp ./clubs_dump mongodb:/tmp/clubs_restore
docker compose exec mongodb sh -c 'mongorestore --username "$MONGO_INITDB_ROOT_USERNAME" --password "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin --db clubs --drop /tmp/clubs_restore'
```

Use a fresh destination directory for each copy to avoid nesting directories or mixing old dump files. `--drop` replaces collections present in the dump, not unrelated collections.

### PostgreSQL

Requires `postgres` running (`docker compose up --wait postgres`).

Dump to a local file (custom archive format):

```bash
docker compose exec -T postgres pg_dump -U postgres -d schedule -Fc > schedule.dump
```

Restore into an existing database. Objects included in the dump are replaced; ownership and grants are omitted for local development:

```bash
docker compose exec -T postgres pg_restore -U postgres -d schedule --clean --if-exists --no-owner --no-privileges --exit-on-error < schedule.dump
```

For a new target database, create it first with `docker compose exec postgres createdb -U postgres schedule`.
