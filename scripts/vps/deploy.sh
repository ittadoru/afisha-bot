#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

export DOCKER_BUILDKIT=1

show_failure_context() {
  printf 'Deployment failed. Recent API and migration logs:\n' >&2
  docker compose logs --no-color --tail 80 api migrate >&2 || true
}
trap show_failure_context ERR

readonly revision_file=".git/afishabot-deployed-revision"
current_revision="$(git rev-parse HEAD)"
previous_revision=""
if [[ -f "$revision_file" ]]; then
  previous_revision="$(cat "$revision_file")"
fi

changed_files=""
if [[ -n "$previous_revision" ]] && git cat-file -e "$previous_revision^{commit}" 2>/dev/null; then
  changed_files="$(git diff --name-only "$previous_revision" "$current_revision")"
fi

build_services=()
if [[ -z "$previous_revision" ]] || [[ -z "$changed_files" ]]; then
  # The first optimized deployment verifies both application images. An empty
  # diff on later deployments means no image rebuild is required.
  if [[ -z "$previous_revision" ]]; then
    build_services=(api frontend nginx)
  fi
else
  if grep -Eq '^compose\.yaml$' <<<"$changed_files"; then
    build_services=(api frontend nginx)
  elif grep -Eq '^(src/|migrations/|Dockerfile$|pyproject\.toml$|uv\.lock$|alembic\.ini$)' \
      <<<"$changed_files"; then
    build_services+=(api)
  fi
  if [[ " ${build_services[*]} " != *" frontend "* ]] \
      && grep -Eq '^(frontend/)' <<<"$changed_files"; then
    build_services+=(frontend)
  fi
  if [[ " ${build_services[*]} " != *" nginx "* ]] \
      && grep -Eq '^(frontend/Dockerfile$)' <<<"$changed_files"; then
    build_services+=(nginx)
  fi
fi

if ((${#build_services[@]})); then
  printf 'Building changed images: %s\n' "${build_services[*]}"
  docker compose build "${build_services[@]}"
else
  printf 'Application images are unchanged; skipping build.\n'
fi

printf 'Starting data services...\n'
docker compose up --detach --wait postgres redis

printf 'Applying database migrations once...\n'
docker compose run --rm migrate

printf 'Starting application services...\n'
compose_profiles=()
application_services=(api bot frontend nginx)
if [[ -f var/nominatim/.import-complete ]]; then
  compose_profiles=(--profile geo)
  application_services+=(nominatim)
fi
docker compose "${compose_profiles[@]}" up --detach --wait --remove-orphans \
  "${application_services[@]}"

# These services have no tasks yet. Stopping old containers also prevents
# restart policies from bringing them back after the next VPS reboot.
docker compose stop worker beat 2>/dev/null || true

printf '%s\n' "$current_revision" >"$revision_file"
trap - ERR
printf 'Deployment complete.\n'
