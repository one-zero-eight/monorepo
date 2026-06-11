# MVP v0 Report

## Purpose

Runnable FastAPI service foundation for future When2Meet development.

## Deployment URL or runnable artifact

TODO: add deployment URL or runnable artifact link.

## Local setup

Run from the monorepo root:

```bash
uv run -m src.when2meet --reload
```

## Smoke check

1. Open `http://localhost:8020/health`.
2. Expected result: `{"status":"ok"}`.
3. Open `http://localhost:8020/docs`.
4. Expected result: Swagger UI loads.

## Limitations

No product behavior is implemented yet.
