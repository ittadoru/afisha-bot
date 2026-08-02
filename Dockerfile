# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE=python:3.14.6-slim
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.8.15

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
RUN apt-get update \
    && apt-get install --yes --no-install-recommends libvips42 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 afisha \
    && useradd --system --uid 10001 --gid afisha --home /app afisha
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./

FROM base AS runtime
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev \
    && mkdir -p /var/lib/afisha/media \
    && chown -R afisha:afisha /app /var/lib/afisha
USER 10001:10001
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "afishabot.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS checks
RUN uv sync --locked --all-groups --no-install-project
COPY . .
RUN uv sync --locked --all-groups
USER 10001:10001
CMD ["/bin/sh", "-c", "uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest && uv run pip-audit && uv run bandit -q -r src"]
