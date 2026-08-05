#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

export DOCKER_BUILDKIT=1

printf 'Building changed application images...\n'
docker compose build api frontend nginx

printf 'Starting data services...\n'
docker compose up --detach --wait postgres redis

printf 'Applying database migrations once...\n'
docker compose run --rm migrate

printf 'Starting application services...\n'
docker compose up --detach --wait --remove-orphans api bot frontend nginx

# These services have no tasks yet. Stopping old containers also prevents
# restart policies from bringing them back after the next VPS reboot.
docker compose stop worker beat 2>/dev/null || true

printf 'Deployment complete.\n'
