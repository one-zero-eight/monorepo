## Testing

### Main principle

Write tests that verify user-visible behavior and service contracts, not incidental implementation details.

Prefer realistic integration tests when they are practical. Use mocks only at system boundaries: external APIs, third-party services, and nondeterministic or external network dependencies.

### Running tests

Run commands from the repository root. Use Docker Compose **5.3.1** (minimum **5.3.0**) and ensure the shared test infrastructure is running:

```bash
docker compose -f docker-compose.test.yaml up --wait
```

Note that the test infrastructure will be stopped after 1 hour of inactivity. If the developer already started it, reuse it rather than starting another stack.

Run tests for one service (preferred; matches CI):

```bash
uv run -m pytest tests/clubs/
```

CI runs each suite in a separate job/process. Do not rely on a single
`uv run -m pytest` across multiple Beanie services — shared `BeanieDocument`
class state in one process can break inserts.

Run the migration CLI suite separately from the service suites:

```bash
uv run -m pytest tests/migrations/
uv run -m pytest tests/when2meet/
uv run -m pytest tests/schedule/
uv run -m pytest tests/schedule_assistant/
```

Useful variants (replace `clubs` with the service under test):

```bash
uv run -m pytest tests/clubs/ --lf
uv run -m pytest tests/clubs/ -k "some expression"
uv run -m pytest tests/path/to/test_file.py
uv run -m pytest tests/path/to/test_file.py::test_name
uv run -m pytest tests/clubs/ -n auto --dist=loadscope
uv run -m pytest tests/clubs/ --cov=src/clubs --cov-report=term-missing
```

### Test design

Good tests should be:

* independent from test order
* explicit about expected behavior
* small enough to identify the broken feature
* realistic enough to catch integration bugs
* stable under parallel execution

Avoid tests that depend on hidden global state, production services, arbitrary sleeps, or exact ordering unless ordering is part of the API contract.

### Infrastructure

Use shared test infrastructure and existing fixtures. Tests and fixtures must not launch Docker or start databases, object stores, or service containers internally. The developer starts `docker-compose.test.yaml`; CI uses native GitHub Actions `services` for PostgreSQL, MongoDB, and MinIO, without Compose or lazytainer. GitHub manages CI service startup and cleanup.

The local stack uses lazytainer. Both environments expose MongoDB `37017`, MinIO API `19000`, MinIO console `19001`, and PostgreSQL `35432`. These differ from the development stack ports, so both local stacks can run together. Locally, reuse the shared stack across service suites; in CI, each suite job gets its own service containers.

MongoDB runs as an authenticated single-node replica set `rs0` locally and in CI so Beanie migration transactions work. Locally, `scripts/mongodb/entrypoint.sh` generates an authentication key in the persistent `/data/configdb` volume. CI creates an ephemeral key in the service command because containers start before checkout. Both use `scripts/mongodb/ready.js` to bootstrap an uninitialized replica set once and report readiness only after it is a writable primary; CI copies the script into its MongoDB container after checkout and waits up to 180 seconds before pytest. Host connections use `directConnection=true&replicaSet=rs0`. Preserve existing local data/config volumes; never delete them to work around migration or readiness failures.

Tests should run against test settings only. Never hardcode production credentials, URLs, buckets, databases, or tokens. CLI subprocess tests must pass a temporary test settings file through `SETTINGS_PATH`, rather than reading the developer's `settings.yaml`.

When parallel test execution is enabled, assume multiple workers may run tests at the same time. Use isolated names, unique test data, or existing cleanup fixtures. Compare the resolved database targets before migration tests: different services and concurrent runs must not share a database or migration history. Do not run two migration runners against the same database simultaneously.

### Migration tests

- `tests/migrations/` covers the settings-aware CLI and its routing to stock Beanie/Alembic, including rejection of unknown, unconfigured, and non-database services. Keep it in a separate pytest process from service suites.
- Service migration tests must exercise both an empty database and populated previous revisions, then check the resulting schema, data, and stock migration history. Keep published revisions and their frozen historical models unchanged.
- MongoDB migration tests use the shared replica set and real transactions. Check safe repeated execution, including retries after data changes but before history is saved: Beanie records history **after** the data transaction commits, not atomically with it. There is no exactly-once guarantee.
- `schedule` and `schedule_assistant` fixtures provision isolated PostgreSQL databases **before** applying the existing Alembic history to head, then start the API. Do not use `create_all()` as a substitute for upgrades or blindly `stamp head`. Retain the existing histories and cover populated upgrade paths as well as empty initialization.

See [Database migrations](README.md#database-migrations) for startup, serialization, and rollback rules.

### Mocking

Mock external systems, not the code under test.

Acceptable mock targets include:

* external HTTP APIs
* authentication providers
* third-party services
* time-sensitive or nondeterministic boundaries

Avoid mocking internal repositories, services, or business logic when the behavior can be tested through the public API.

You could use `respx` for mocking external HTTP APIs, you can search for examples in the repository.

### Assertions

Assert outcomes, not implementation steps.

Prefer:

```python
assert response.status_code == 404
assert response.json()["detail"] == "Club not found"
```

Over:

```python
assert some_internal_function_was_called
```

For successful responses, assert the fields that define correctness. Avoid asserting entire payloads when only a few fields matter.

### Test data

Use clear, minimal test data.

When creating persistent records, files, buckets, objects, slugs, or IDs, make them unique unless the test specifically verifies conflicts.

Do not rely on data created by another test.

### External network

Tests must not call real external services. All external network interactions should be mocked, stubbed, or routed through controlled test infrastructure.

### Debugging

For visible output:

```bash
uv run -m pytest tests/clubs/ -s
```

For verbose output:

```bash
uv run -m pytest tests/clubs/ -vv
```

For one failing test:

```bash
uv run -m pytest tests/path/to/test_file.py::test_name -vv -s
```

### Coverage

Coverage is useful for finding untested areas, but it is not the goal by itself.

Prefer meaningful tests for important behavior over shallow tests written only to increase coverage numbers.


### Commit messages

Use `test(service, ...): description` or `test: description` format for commit messages when adding or updating only tests or test infrastructure.
