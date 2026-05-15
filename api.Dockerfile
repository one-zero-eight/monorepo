###########################################################
# Builder stage. Build dependencies.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_NO_DEV=1

WORKDIR /app
COPY ./pyproject.toml ./uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev


###########################################################
# Production stage.
FROM python:3.14-slim-bookworm AS production

ARG APP_MODULE
ENV APP_MODULE=${APP_MODULE}

ARG WORKERS=1
ENV WORKERS=${WORKERS}

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/app/.venv/bin:$PATH"

RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libmagic1 \
        libvips-dev \
    && rm -rf /var/lib/apt/lists/*


RUN groupadd -g 1500 uv && \
    useradd -m -u 1500 -g uv uv


COPY --chown=uv:uv . /app
COPY --from=builder --chown=uv:uv /app/.venv /app/.venv

WORKDIR /app

USER uv

EXPOSE 8000
CMD ["sh", "-c", "exec gunicorn --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers \"$WORKERS\" \"$APP_MODULE\" --timeout 300 --forwarded-allow-ips=*"]
