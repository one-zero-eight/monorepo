Run infra via `docker compose up -d mongodb minio`.

Create `settings.yaml` in monorepo root via `cp settings.example.yaml settings.yaml`. Edit settings in `settings.yaml` if needed.

Run service via `uv run -m src.maps`.

Tests run only via `uv run -m pytest` or `python -m pytest`, not `pytest`.
