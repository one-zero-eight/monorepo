Run infra via `docker compose up --wait mongodb minio`.

Create `settings.yaml` in monorepo root via `cp settings.example.yaml settings.yaml`. Edit settings in `settings.yaml` if needed.

Run service via `uv run -m src.maps`.


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
