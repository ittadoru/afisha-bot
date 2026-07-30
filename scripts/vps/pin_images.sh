#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

output="deploy/image-digests.env"
: >"$output"

pin() {
  local variable="$1"
  local image="$2"
  docker pull --platform linux/amd64 "$image" >/dev/null
  local digest
  digest="$(docker image inspect "$image" --format '{{index .RepoDigests 0}}')"
  [[ "$digest" == *@sha256:* ]] || {
    printf 'No immutable digest resolved for %s\n' "$image" >&2
    exit 1
  }
  printf '%s=%s\n' "$variable" "$digest" >>"$output"
}

pin POSTGIS_IMAGE postgis/postgis:18-3.6
pin REDIS_IMAGE redis:8.2-alpine
pin NGINX_IMAGE nginx:1.29-alpine
pin NOMINATIM_IMAGE mediagis/nominatim:5.3
pin PROMETHEUS_IMAGE prom/prometheus:v3.5.0
pin ALERTMANAGER_IMAGE prom/alertmanager:v0.28.1
pin NODE_EXPORTER_IMAGE prom/node-exporter:v1.9.1
pin PYTHON_IMAGE python:3.14.6-slim
pin UV_IMAGE ghcr.io/astral-sh/uv:0.8.15
pin GITLEAKS_IMAGE ghcr.io/gitleaks/gitleaks:v8.28.0
pin TRIVY_IMAGE aquasec/trivy:0.65.0
pin SYFT_IMAGE anchore/syft:v1.30.1

printf 'Pinned references written to %s. Review and commit them.\n' "$output"
