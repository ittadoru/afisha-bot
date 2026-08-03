#!/usr/bin/env bash
set -Eeuo pipefail

readonly venv_bin="/app/.venv/bin"

run_step() {
  local name="$1"
  shift
  printf 'G6 backend check: %s\n' "$name"
  "$@"
}

export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-/tmp/ruff-cache}"
export COVERAGE_FILE="${COVERAGE_FILE:-/tmp/.coverage}"
export VIRTUAL_ENV="/app/.venv"
export PATH="$venv_bin:$PATH"

run_step ruff-format "$venv_bin/ruff" format --check .
run_step ruff-lint "$venv_bin/ruff" check .
run_step pyright-strict "$venv_bin/pyright"
run_step pytest-coverage \
  "$venv_bin/pytest" -o cache_dir=/tmp/pytest-cache
run_step bandit-sast "$venv_bin/bandit" -q -lll -r src

printf 'G6 backend checks passed\n'
