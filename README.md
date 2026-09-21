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
   See [DATABASE.md](DATABASE.md) for details.
7. Start development server (and read logs in the terminal).

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

Apply pending migrations from the repository root before starting a database-backed service:

```bash
uv run -m src.migrations clubs && uv run -m src.clubs --reload
```

See [DATABASE.md](DATABASE.md) for supported services, MongoDB and PostgreSQL migrations, deployment, and dump/restore commands.

### Testing

Testing guidelines, infrastructure details, and common pytest commands are documented in [TESTING.md](./TESTING.md).

Start the shared MongoDB, MinIO, and PostgreSQL test infrastructure:

```bash
docker compose -f docker-compose.test.yaml up --wait
```

The local lazytainer stack stops after one hour of inactivity. Tests and fixtures never launch Docker internally. CI uses native GitHub Actions `services` with the same images, test credentials, and host ports, without Compose/lazytainer setup or teardown steps.

Run all tests from the repository root in one invocation:

```bash
uv run -m pytest
```

You can also select multiple suites or enable parallel workers:

```bash
uv run -m pytest tests/clubs/ tests/when2meet/
uv run -m pytest -n auto --dist=loadscope
```

For another service, replace the suite path. To rerun only failed tests within a suite:

```bash
uv run -m pytest tests/clubs/ --lf
```

### How to update dependencies

1. Run `uv sync --upgrade` to update uv.lock file and install the latest versions of the dependencies.
2. Run `uv tree --outdated --depth=1` will show what package versions are installed and what are the latest versions.
3. Run `uv run prek auto-update` to update prek hooks.

Also, Dependabot will help you to keep your dependencies up-to-date, see [dependabot.yaml](.github/dependabot.yaml).

### Adding a new service

If you need to scaffold a new service, use the [NEW_SERVICE.md](NEW_SERVICE.md) guide.
