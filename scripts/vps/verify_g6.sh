#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

current_step="initialization"

announce() {
  current_step="$1"
  printf '\nG6 step: %s\n' "$1"
}

report_failure() {
  local status="$?"
  printf 'G6 failed: step=%s line=%s exit=%s\n' \
    "$current_step" "${BASH_LINENO[0]}" "$status" >&2
  exit "$status"
}

trap report_failure ERR

bash scripts/vps/preflight.sh

sha="$(git rev-parse HEAD)"
upstream_sha="$(git rev-parse '@{upstream}')"
[[ "$sha" == "$upstream_sha" ]] || {
  printf 'HEAD %s does not match upstream %s\n' "$sha" "$upstream_sha" >&2
  exit 1
}

[[ -s deploy/image-digests.env ]] || {
  printf 'Run pin_images.sh, review and commit deploy/image-digests.env first.\n' >&2
  exit 1
}
git ls-files --error-unmatch deploy/image-digests.env >/dev/null || {
  printf 'deploy/image-digests.env must be committed before verification.\n' >&2
  exit 1
}
if grep -Evq \
  '^[A-Z0-9_]+=[^@[:space:]]+@sha256:[0-9a-f]{64}$' \
  deploy/image-digests.env; then
  printf 'deploy/image-digests.env contains a placeholder or floating tag.\n' >&2
  exit 1
fi

set -a
source deploy/image-digests.env
set +a

for ref in \
  "$POSTGIS_IMAGE" "$REDIS_IMAGE" "$NGINX_IMAGE" "$NOMINATIM_IMAGE" \
  "$PROMETHEUS_IMAGE" "$ALERTMANAGER_IMAGE" "$NODE_EXPORTER_IMAGE" \
  "$NODE_IMAGE" "$PYTHON_IMAGE" "$UV_IMAGE" "$GITLEAKS_IMAGE" "$TRIVY_IMAGE" \
  "$SYFT_IMAGE"; do
  [[ "$ref" == *@sha256:* ]] || {
    printf 'Floating image reference rejected: %s\n' "$ref" >&2
    exit 1
  }
done

export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1
export AFISHA_APP_IMAGE="${AFISHA_APP_IMAGE:-afishabot-g6:local}"
export AFISHA_FRONTEND_IMAGE="${AFISHA_FRONTEND_IMAGE:-afishabot-frontend-g6:local}"
export POSTGRES_USER="${POSTGRES_USER:-afisha}"
export POSTGRES_DB="${POSTGRES_DB:-afisha}"
export COMPOSE_PROJECT_NAME="afisha_g6_${sha:0:12}"

cleanup() {
  docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
mkdir -p artifacts/g6

announce compose-config
docker compose config --quiet
docker compose config --format json >artifacts/g6/compose.json
python3 - <<'PY'
import json
from pathlib import Path

services = json.loads(
    Path("artifacts/g6/compose.json").read_text(encoding="utf-8")
)["services"]
for name in ("postgres", "redis"):
    if services[name].get("ports"):
        raise SystemExit(f"{name} must not publish host ports")

media_users = {
    name
    for name, service in services.items()
    if any(
        volume.get("source") == "media_data"
        for volume in service.get("volumes", [])
    )
}
if media_users != {"api", "worker"}:
    raise SystemExit(f"media_data scope is unsafe: {sorted(media_users)}")

nginx_ports = services["nginx"].get("ports", [])
if len(nginx_ports) != 1 or nginx_ports[0].get("host_ip") != "127.0.0.1":
    raise SystemExit("Nginx must publish only a loopback staging port")
PY

announce backend-images
docker build \
  --build-arg "PYTHON_IMAGE=$PYTHON_IMAGE" \
  --build-arg "UV_IMAGE=$UV_IMAGE" \
  --target checks \
  --tag afishabot-g6-checks:verify \
  .
docker build \
  --build-arg "PYTHON_IMAGE=$PYTHON_IMAGE" \
  --build-arg "UV_IMAGE=$UV_IMAGE" \
  --target runtime \
  --tag "$AFISHA_APP_IMAGE" \
  .

announce frontend-images
docker build \
  --build-arg "NODE_IMAGE=$NODE_IMAGE" \
  --build-arg "NGINX_IMAGE=$NGINX_IMAGE" \
  --target checks \
  --tag afishabot-frontend-checks:verify \
  --file frontend/Dockerfile \
  .
docker build \
  --build-arg "NODE_IMAGE=$NODE_IMAGE" \
  --build-arg "NGINX_IMAGE=$NGINX_IMAGE" \
  --target runtime \
  --tag "$AFISHA_FRONTEND_IMAGE" \
  --file frontend/Dockerfile \
  .

announce migrations-and-backend-checks
docker compose up --detach --wait postgres redis
docker compose run --rm migrate
docker compose --profile verify run --rm checks

announce dependency-audit
docker run --rm \
  --read-only \
  --tmpfs /tmp:size=128m,mode=1777 \
  --network bridge \
  afishabot-g6-checks:verify \
  /app/.venv/bin/pip-audit \
  --local --skip-editable --cache-dir /tmp/pip-audit-cache
docker run --rm \
  --read-only \
  --tmpfs /tmp:size=128m,mode=1777 \
  --network bridge \
  --env npm_config_cache=/tmp/npm-cache \
  afishabot-frontend-checks:verify \
  npm audit --audit-level=high

announce runtime-services
docker compose up --detach --wait api worker beat frontend nginx

announce health-and-boundaries
curl --fail --silent --show-error http://127.0.0.1:8080/health/live >/dev/null
curl --fail --silent --show-error http://127.0.0.1:8080/health/ready >/dev/null
metrics_status="$(curl --silent --output /dev/null --write-out '%{http_code}' http://127.0.0.1:8080/metrics)"
[[ "$metrics_status" == "404" ]] || {
  printf 'Nginx exposed /metrics with status %s\n' "$metrics_status" >&2
  exit 1
}
for path in / /app /admin; do
  status="$(
    curl --silent --output /dev/null --write-out '%{http_code}' \
      "http://127.0.0.1:8080${path}"
  )"
  [[ "$status" == "200" ]] || {
    printf 'Frontend route %s returned %s instead of 200\n' \
      "$path" "$status" >&2
    exit 1
  }
done

announce migrations-postgis-and-celery
heads="$(docker compose run --rm api /app/.venv/bin/alembic heads | wc -l | tr -d ' ')"
[[ "$heads" == "1" ]] || {
  printf 'Expected one Alembic head, found %s\n' "$heads" >&2
  exit 1
}

docker compose exec -T postgres psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --tuples-only \
  --command "SELECT extname FROM pg_extension WHERE extname='postgis';" \
  | grep -q postgis
schema_count="$(
  docker compose exec -T postgres psql \
    --username "$POSTGRES_USER" \
    --dbname "$POSTGRES_DB" \
    --tuples-only \
    --no-align \
    --command "SELECT count(*) FROM information_schema.schemata WHERE schema_name IN ('accounts','discovery','events','communication','trust_safety','reputation','media');"
)"
[[ "$schema_count" == "7" ]] || {
  printf 'Expected seven owner schemas, found %s\n' "$schema_count" >&2
  exit 1
}

docker compose exec -T worker /app/.venv/bin/celery \
  -A afishabot.adapters.tasks.celery_app:celery_app inspect ping \
  --timeout 10 | grep pong >/dev/null
docker compose exec -T worker python --version | grep -q 'Python 3.14.6'

for service in api worker beat; do
  container_id="$(docker compose ps --quiet "$service")"
  user="$(docker inspect "$container_id" --format '{{.Config.User}}')"
  [[ "$user" == "10001:10001" ]] || {
    printf '%s is not configured as the application user\n' "$service" >&2
    exit 1
  }
done
for service in postgres redis api worker beat frontend nginx; do
  container_id="$(docker compose ps --quiet "$service")"
  memory_limit="$(docker inspect "$container_id" --format '{{.HostConfig.Memory}}')"
  [[ "$memory_limit" -gt 0 ]] || {
    printf '%s has no enforced memory limit\n' "$service" >&2
    exit 1
  }
done

announce security-scans-and-sbom
docker run --rm --volume "$repo_root:/src:ro" \
  "$GITLEAKS_IMAGE" detect --source=/src
docker save --output artifacts/g6/app-image.tar "$AFISHA_APP_IMAGE"
docker save --output artifacts/g6/frontend-image.tar "$AFISHA_FRONTEND_IMAGE"
docker run --rm --volume "$repo_root/artifacts/g6:/scan:ro" \
  "$TRIVY_IMAGE" image --input /scan/app-image.tar \
  --severity HIGH,CRITICAL --exit-code 1
docker run --rm --volume "$repo_root/artifacts/g6:/scan:ro" \
  "$TRIVY_IMAGE" image --input /scan/frontend-image.tar \
  --severity HIGH,CRITICAL --exit-code 1
docker run --rm --volume "$repo_root/artifacts/g6:/scan:ro" \
  "$SYFT_IMAGE" docker-archive:/scan/app-image.tar -o cyclonedx-json \
  >artifacts/g6/backend-sbom.cdx.json
docker run --rm --volume "$repo_root/artifacts/g6:/scan:ro" \
  "$SYFT_IMAGE" docker-archive:/scan/frontend-image.tar -o cyclonedx-json \
  >artifacts/g6/frontend-sbom.cdx.json

app_image_id="$(docker image inspect "$AFISHA_APP_IMAGE" --format '{{.Id}}')"
frontend_image_id="$(
  docker image inspect "$AFISHA_FRONTEND_IMAGE" --format '{{.Id}}'
)"
migration_head="$(docker compose run --rm api /app/.venv/bin/alembic heads | awk '{print $1}')"
timestamp="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

announce evidence-manifest
python3 - \
  "$sha" "$app_image_id" "$frontend_image_id" "$migration_head" "$timestamp" <<'PY'
import json
import sys
from pathlib import Path

sha, app_image_id, frontend_image_id, migration_head, timestamp = sys.argv[1:]
manifest = {
    "schema_version": 1,
    "commit_sha": sha,
    "application_image_id": app_image_id,
    "frontend_image_id": frontend_image_id,
    "external_image_references": {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in Path("deploy/image-digests.env").read_text(
            encoding="utf-8"
        ).splitlines()
        if line and not line.startswith("#")
    },
    "migration_head": migration_head,
    "checked_at_utc": timestamp,
    "checks": [
        "locked_dependencies",
        "ruff_format",
        "ruff_lint",
        "pyright_strict",
        "pytest_coverage_75",
        "frontend_vitest_build_storybook",
        "architecture_imports",
        "alembic_single_head_empty_upgrade",
        "postgres_postgis",
        "redis_celery",
        "nginx_boundary",
        "dependency_sast_secret_scans",
        "backend_frontend_sbom_container_scan",
        "compose_health_resources",
    ],
    "result": "passed",
}
Path("artifacts/g6/manifest.json").write_text(
    json.dumps(manifest, indent=2) + "\n",
    encoding="utf-8",
)
PY

printf 'G6 authoritative gate passed for %s\n' "$sha"
