# InNoHassle monorepo

## Table of contents

Did you know that GitHub supports table of
contents [by default](https://github.blog/changelog/2021-04-13-table-of-contents-support-in-markdown-files/) 🤔


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
- When2Meet - service for meeting availability planning. Hosted docs: [one-zero-eight.github.io/monorepo](https://one-zero-eight.github.io/monorepo/), development process: [docs/development-process.md](src/when2meet/docs/development-process.md), architecture: [docs/architecture/README.md](src/when2meet/docs/architecture/README.md), Week 5 report: [reports/week5](https://github.com/one-zero-eight/monorepo/tree/main/src/when2meet/reports/week5).

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

1. Install [uv](https://docs.astral.sh/uv/) and [Docker](https://docs.docker.com/engine/install/)
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
5. Create `settings.yaml` in monorepo and set up accounts API JWT token:
   ```bash
   uv run scripts/prepare.py
   ```
6. Start development server (and read logs in the terminal):

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
   uv run -m src.guard --reload
   ```
   > It will be available at http://localhost:8013

   For clubs service:
   ```bash
   uv run -m src.clubs --reload
   ```
   > It will be available at http://localhost:8014

   For student affairs service:
   ```bash
   uv run -m src.student_affairs --reload
   ```
   > It will be available at http://localhost:8015

   For forms service:
   ```bash
   uv run -m src.forms --reload
   ```
   > It will be available at http://localhost:8017

   For when2meet service:
   ```bash
   uv run -m src.when2meet --reload
   ```
   > It will be available at http://localhost:8020

   For table tennis service:
   ```bash
   uv run -m src.tabletennis --reload
   ```
   > It will be available at http://localhost:8023

   For schedule service:
   ```bash
   uv run -m src.schedule --reload
   ```
   > It will be available at http://localhost:8024
   </details>


> [!IMPORTANT]
> For endpoints requiring authorization click "Authorize" button in Swagger UI

> [!TIP]
> Edit `settings.yaml` according to your needs, you can view schema in
> [settings.schema.yaml](settings.schema.yaml)

### Testing

Testing guidelines, infrastructure details, and common pytest commands are documented in [TESTING.md](./TESTING.md).

Firstly, start the test infrastructure:

```bash
docker compose -f docker-compose.test.yaml up --wait
```

It will setup mongodb and minio services, note that they will be stopped after 1 hour of inactivity.

Then, run the tests:

```bash
uv run -m pytest
```

In output you will see failing tests, timings, coverage, etc.

To rerun only failed tests, you can use:

```bash
uv run -m pytest --lf
```

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
