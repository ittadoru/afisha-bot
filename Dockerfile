# syntax=docker/dockerfile:1.7
ARG PYTHON_IMAGE=python:3.14.6-alpine3.23
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.8.15

FROM ${UV_IMAGE} AS uv

FROM ${PYTHON_IMAGE} AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
RUN apk add --no-cache vips \
    && addgroup -S -g 10001 afisha \
    && adduser -S -D -H -u 10001 -G afisha afisha
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./

FROM base AS runtime
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --locked --no-dev \
    && mkdir -p /var/lib/afisha/media \
    && chown -R afisha:afisha /app /var/lib/afisha
USER 10001:10001
EXPOSE 8000
CMD ["/app/.venv/bin/uvicorn", "afishabot.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS checks
RUN apk add --no-cache bash nodejs
RUN uv sync --locked --all-groups --no-install-project
COPY . .
RUN uv sync --locked --all-groups
USER 10001:10001
CMD ["bash", "scripts/vps/run_backend_checks.sh"]
