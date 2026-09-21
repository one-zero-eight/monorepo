# InNoHassle Monorepo

## About

This is the monorepo for some of the backend services of InNoHassle ecosystem, all of them are FastAPI ASGI applications.

- Clubs service - Innopolis University student clubs management system to view clubs, add new clubs, and edit their descriptions and logos.
- Forms - managing Yandex Forms links and generating signed prefilled URLs for authenticated users.
- Guard - gating access to Google Spreadsheets by requiring InNoHassle Accounts authentication before adding users.
- Maps - hosting Innopolis University maps to view them on innohassle.ru.
- Room booking - view and manage room bookings at innohassle.ru via integration with Microsoft Outlook.
- Schedule - aggregate university schedules, personalize favorites, and export ICS calendars at [innohassle.ru/schedule](https://innohassle.ru/schedule).
- Schedule Assistant - build and manage academic schedules, validate placement issues.
- Student Affairs - omnidesk authentication via SSO for Student Affairs department to issue tickets.
- Table Tennis - leaderboard and queue for the [Innopolis University table tennis club](https://innohassle.ru/clubs/inno-table-tennis).
- When2Meet - meeting availability planner for the InNoHassle ecosystem.

### Technologies

- [Python 3.14](https://www.python.org/downloads/) & [uv](https://docs.astral.sh/uv/)
- [FastAPI](https://fastapi.tiangolo.com/)
- Database and ORM: [MongoDB](https://www.mongodb.com/) & [Beanie](https://beanie-odm.dev/); [PostgreSQL](https://www.postgresql.org/) & [SQLAlchemy](https://www.sqlalchemy.org/)
- File storage: [MinIO](https://github.com/minio/minio)
- Formatting and linting: [Ruff](https://docs.astral.sh/ruff/), [prek](https://prek.j178.dev/)
- Type checking: [ty](https://docs.astral.sh/ty/)
- Testing: [pytest](https://docs.pytest.org)
- CI/CD: [Docker](https://www.docker.com/), [Docker Compose](https://docs.docker.com/compose/),
  [GitHub Actions](https://github.com/features/actions)

## Contributing

We are open to contributions of any kind.
You can help us with code, bugs, design, documentation, media, new ideas, etc.
If you are interested in contributing, please read
our [contribution guide](https://github.com/one-zero-eight/.github/blob/main/CONTRIBUTING.md).


## Development

### Set up for development

1. Install [uv](https://docs.astral.sh/uv/), [Docker](https://docs.docker.com/engine/install/), and Docker Compose **5.3.1** (minimum **5.3.0**, required for `pre_start` hooks).
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Install prek hooks:
   ```bash
   uv run prek install --overwrite --prepare-hooks -t pre-commit -t commit-msg
   ```
4. Run infra:
   ```bash
   docker compose up --wait mongodb minio
   ```
   For `schedule` or `schedule_assistant`, also start PostgreSQL with `docker compose up --wait postgres`.
5. Create `settings.yaml` in monorepo and set up accounts API JWT token:
   ```bash
   uv run scripts/prepare.py
   ```
6. For a database-backed service, provision its database and apply pending migrations from the repository root before starting its API:
   ```bash
   uv run -m src.migrations clubs
   ```
   Replace `clubs` with the service identifier listed in [Database migrations](#database-migrations). PostgreSQL databases and users must be provisioned separately before migrations. No migration is needed for `maps`, `room_booking`, or `student_affairs`.
7. Start development server (and read logs in the terminal). In VSCode/Cursor or PyCharm, run the same migration command in the terminal **before** starting the debugger; no IDE migration configuration is required.

   <details>
   <summary>For VSCode</summary>
   In the left menu of the IDE go to "Run and Debug" tab, choose the service name and click play button to start the API.
   After that, open the URL from console in your browser to view Swagger.

   **Set up VSCode plugins**

   Go to Extensions and install the following plugins (recommendations in [.vscode/extensions.json](.vscode/extensions.json)):
   - Python (by Microsoft)
   - Ruff (by Charlie Marsh)
   - ty (by astral-sh)

   Also, if you will use **ty** typechecker, you should disable others in VSCode settings:

   ```json
   {
      "python.languageServer": "None",
      "python.analysis.typeCheckingMode": "off",

      "cursorpyright.disableLanguageServices": true,
      "cursorpyright.analysis.typeCheckingMode": "off",

      "basedpyright.disableLanguageServices": true,
      "basedpyright.analysis.typeCheckingMode": "off",

      "pyright.disableLanguageServices": true,
      "pyright.analysis.typeCheckingMode": "off"
   }
   ```

   </details>

   <details>
   <summary>For PyCharm</summary>
   In the top-right corner of the IDE choose the service name and click green play button to start the API ([see docs](https://www.jetbrains.com/help/pycharm/run-debug-configuration.html#createExplicitly)).
   After that, open the URL from console in your browser to view Swagger.

    **Set up PyCharm plugins**

    1. Ruff ([plugin](https://plugins.jetbrains.com/plugin/20574-ruff)).
       It will lint and format your code. Make sure to enable `Use ruff format` option in plugin settings.
    2. Pydantic ([plugin](https://plugins.jetbrains.com/plugin/12861-pydantic)). It will fix PyCharm issues with
       type-hinting.
    3. Conventional commits ([plugin](https://plugins.jetbrains.com/plugin/13389-conventional-commit)). It will help you
       to write [conventional commits](https://www.conventionalcommits.org/en/v1.0.0/).
   </details>

   <details>
   <summary>Using console</summary>

   For room booking service:
   ```bash
   uv run -m src.room_booking --reload
   ```
   > It will be available at http://localhost:8008

   For maps service:
   ```bash
   uv run -m src.maps --reload
   ```
   > It will be available at http://localhost:8009

   For guard service:
   ```bash
   uv run -m src.migrations guard && uv run -m src.guard --reload
   ```
   > It will be available at http://localhost:8013

   For clubs service:
   ```bash
   uv run -m src.migrations clubs && uv run -m src.clubs --reload
   ```
   > It will be available at http://localhost:8014

   For student affairs service:
   ```bash
   uv run -m src.student_affairs --reload
   ```
   > It will be available at http://localhost:8015

   For board games service:
   ```bash
   uv run -m src.migrations board_games && uv run -m src.board_games --reload
   ```
   > It will be available at http://localhost:8016

   For forms service:
   ```bash
   uv run -m src.migrations forms && uv run -m src.forms --reload
   ```
   > It will be available at http://localhost:8017

   For when2meet service:
   ```bash
   uv run -m src.migrations when2meet && uv run -m src.when2meet --reload
   ```
   > It will be available at http://localhost:8020

   For events service:
   ```bash
   uv run -m src.migrations events && uv run -m src.events --reload
   ```
   > It will be available at http://localhost:8021

   For table tennis service:
   ```bash
   uv run -m src.migrations tabletennis && uv run -m src.tabletennis --reload
   ```
   > It will be available at http://localhost:8023

   For schedule service:
   ```bash
   uv run -m src.migrations schedule && uv run -m src.schedule --reload
   ```
   > It will be available at http://localhost:8024

   For schedule assistant service:
   ```bash
   uv run -m src.migrations schedule_assistant && uv run -m src.schedule_assistant --reload
   ```
   > It will be available at http://localhost:8012
   </details>


> [!IMPORTANT]
> For endpoints requiring authorization click "Authorize" button in Swagger UI

> [!TIP]
> Edit `settings.yaml` according to your needs, you can view schema in
> [settings.schema.yaml](settings.schema.yaml)

### Database migrations

From the repository root, apply all pending forward migrations for one configured service:

```bash
uv run -m src.migrations clubs
```

The supported identifiers are `board_games`, `clubs`, `events`, `forms`, `guard`, `tabletennis`, `when2meet`, `schedule`, and `schedule_assistant`. Use Python package names with underscores, not Compose names such as `board-games`. Unknown identifiers, missing service settings, and services without a database are errors; `maps`, `room_booking`, and `student_affairs` do not need migrations.

The CLI reads `settings.yaml` through the same settings loader as the API; `SETTINGS_PATH` overrides that path. When using a custom file, set it for **both** the migration and API processes, for example with `export SETTINGS_PATH=/absolute/path/settings.yaml`. Check the resolved database host and name before applying migrations, especially when switching environments. MongoDB uses the database in the configured URI, or the service's default database name when omitted (`when2meet_service.service_name` supplies the When2Meet default). Use a separate logical database for each service: Beanie's `migrations_log` is database-wide. Keep different services' database targets and histories isolated.

This is a thin adapter over stock Beanie for the seven MongoDB services and stock Alembic `upgrade head` for `schedule` and `schedule_assistant`. Beanie revisions live in `src/<service>/migrations/`; SQL services retain their existing Alembic directories, revision IDs, and histories. Provision PostgreSQL databases/users before migrations; a healthy PostgreSQL container alone does not create the configured service databases. Do not replace Alembic upgrades with `create_all()` or blindly use `stamp head` on an existing database.

The shared CLI is **forward-only**. Create revisions with the stock tools, then review the generated code:

```bash
uv run beanie new-migration -n describe_change -p src/clubs/migrations
uv run alembic -c src/schedule/alembic.ini revision --autogenerate -m "describe change"
uv run alembic -c src/schedule_assistant/alembic.ini revision --autogenerate -m "describe change"
```

Beanie filenames must retain their timestamp and must not begin with `_`, which the runner skips. Keep published revisions and frozen historical models unchanged; express later changes as new revisions instead of runtime legacy normalization. Do not create fake baseline migrations for services without data changes. Test upgrades from both empty databases and populated previous revisions. See the [Alembic instructions](src/schedule/alembic/README.md) for schema checks and onboarding an unversioned database.

Beanie runs with transactions enabled and automatic index dropping forbidden. Normal application index initialization still happens **after** migrations. Handle conflicting indexes explicitly (prepare data, then change the index); index DDL is not covered by the data transaction's rollback. Do not automatically deduplicate documents or rename collections such as `Tournament_v2`.

After pulling a new migration, **stop the development server, apply migrations, then restart it**. `--reload` reloads application code; it does not apply migrations. The console examples above use `&&` so the API starts only after a successful migration. In an IDE, run the migration command in the terminal before starting or restarting the debug session.

#### MongoDB replica set

Beanie migrations use transactions, so MongoDB must be a replica set. Local development, shared tests, and CI use an authenticated single-node `rs0`. Locally, `scripts/mongodb/entrypoint.sh` generates the authentication key once in the persistent `/data/configdb` volume. CI uses native GitHub Actions service containers and creates an ephemeral key in the MongoDB service command, since containers start before checkout. Both environments use `scripts/mongodb/ready.js`: it initializes an unconfigured replica set once, never rewrites an existing replica configuration, and reports ready only when the node is a writable primary. CI copies this script into its MongoDB container after checkout and waits up to 180 seconds before running tests.

The default host URI is `mongodb://onezeroeight:herewethinkbig@127.0.0.1:27017/?authSource=admin&directConnection=true&replicaSet=rs0`. Direct connection lets host tools use the published port without following the container-only advertised hostname. If you set an explicit local URI in `settings.yaml`, include `directConnection=true&replicaSet=rs0`; tests use their own credentials and port `37017`.

Production must use its **actual replica-set topology**, credentials, and reachable member addresses, not a forced copy of the local single-node setup or its direct-connection defaults. Converting an existing standalone database requires a separate backed-up operational procedure. Preserve existing data and config volumes; never delete volumes to enable migrations or fix replica-set readiness.

#### Compose startup and deployment

Use Docker Compose **5.3.1** (minimum **5.3.0**). Each of the nine database-backed API services has a `pre_start` hook running `python -m src.migrations <service>` in its image with its settings. The hook must succeed before API startup; failure blocks startup. Migrations are never run from application lifespan or individual workers, and no separate one-shot migration service is needed.

Hooks run on container creation/recreation, including deployment of a new image. A normal `docker compose restart` or scaling operation is **not** a migration trigger; do not use either to apply a newly pulled revision. Deploy new revisions through recreation/new-image startup or run the CLI explicitly before restarting a stopped local API.

There are **no custom locks or exactly-once guarantees**. Serialize deployments for each environment, and forbid simultaneous manual migrations or competing deployments against the same database. Beanie commits the data transaction **before** saving migration history: a crash in that gap can cause the same revision to run again. Write idempotent migrations; transactions alone do not make history and data atomic.

Before deployment, verify target database isolation, take a backup, review pending revisions and rollback options, and ensure the deployer waits for the migration gate before serving traffic. Stop old writers, including background jobs, before incompatible data changes: `pre_start` does not guarantee that they have stopped and does not make a multi-database rollout atomic. Do not automatically migrate backward when an image rolls back. Before starting an older image, inspect database history, especially Beanie entries for revision files absent from that image; do not assume unknown history is safely rejected. Compare the current and rollback images' histories against isolated database targets first. Use an explicit stock downgrade only when it is supported and data-safe; for irreversible migrations, restore a verified backup or ship a forward fix.

For `schedule_assistant` revision `o5i6j7k8l9m0`, which drops `config_history_events`, take a fresh Postgres backup, stop every old `schedule_assistant` writer, apply the migration, then start the new image. Do not run that drop while older writers are still inserting history rows. Downgrade is intentionally unsupported; recover history only from the verified backup.

**Staging/production deployer verification remains outstanding:** the external deployment system must be checked for Compose version, hook execution/failure gating on new images, deployment serialization, actual database topology/targets, and rollback behavior. Check both targeted and `all` deployments: the hook must use the requested new image digest, recreate the service, wait for completion, and propagate failure to the workflow. The repository workflow serializes both modes per environment; it cannot validate the external implementation. Repository changes and local/CI checks do not establish that production satisfies this contract.

### Testing

Testing guidelines, infrastructure details, and common pytest commands are documented in [TESTING.md](./TESTING.md).

Start the shared MongoDB, MinIO, and PostgreSQL test infrastructure:

```bash
docker compose -f docker-compose.test.yaml up --wait
```

The local lazytainer stack stops after one hour of inactivity. Tests and fixtures never launch Docker internally. CI uses native GitHub Actions `services` with the same images, test credentials, and host ports, without Compose/lazytainer setup or teardown steps.

Run each suite in a **separate process** from the repository root, not a single pytest invocation across Beanie services:

```bash
uv run -m pytest tests/clubs/
uv run -m pytest tests/when2meet/
uv run -m pytest tests/schedule/
uv run -m pytest tests/schedule_assistant/
```

For another service, replace the suite path. Shared Beanie document state can break combined suites. To rerun only failed tests within a suite:

```bash
uv run -m pytest tests/clubs/ --lf
```

### Git worktrees

To work on several branches in parallel without stashing or switching in the main checkout, see [WORKTREE.md](./WORKTREE.md).

### How to update dependencies

1. Run `uv sync --upgrade` to update uv.lock file and install the latest versions of the dependencies.
2. Run `uv tree --outdated --depth=1` will show what package versions are installed and what are the latest versions.
3. Run `uv run prek auto-update` to update prek hooks.

Also, Dependabot will help you to keep your dependencies up-to-date, see [dependabot.yaml](.github/dependabot.yaml).

### How to dump the database

Requires `mongodb` running (`docker compose up --wait mongodb`).

1. Dump (f.e. /clubs database):
   ```bash
   docker compose exec mongodb sh -c 'mongodump "mongodb://$MONGO_INITDB_ROOT_USERNAME:$MONGO_INITDB_ROOT_PASSWORD@127.0.0.1:27017/clubs?authSource=admin" --db=clubs --out=dump/'
   docker compose cp mongodb:/dump/clubs ./clubs_dump
   ```
2. Restore (f.e. /clubs database):
   ```bash
   docker compose exec mongodb sh -c 'mongorestore "mongodb://$MONGO_INITDB_ROOT_USERNAME:$MONGO_INITDB_ROOT_PASSWORD@127.0.0.1:27017/clubs?authSource=admin" --drop dump/clubs'
   docker compose cp ./clubs_dump mongodb:/dump/clubs
   ```

### Adding a new service

If you need to scaffold a new service, use the [NEW_SERVICE.md](NEW_SERVICE.md) guide.
