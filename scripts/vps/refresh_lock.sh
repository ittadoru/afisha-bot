#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git diff --quiet && git diff --cached --quiet || {
  printf 'Lock refresh requires no tracked changes.\n' >&2
  exit 1
}

[[ -f deploy/image-digests.env ]] || {
  printf 'Run pin_images.sh first so uv itself is digest-pinned.\n' >&2
  exit 1
}

set -a
source deploy/image-digests.env
set +a

docker run --rm \
  --user "$(id -u):$(id -g)" \
  --volume "$repo_root:/workspace" \
  --workdir /workspace \
  "$UV_IMAGE" \
  uv lock --python 3.14.6

printf 'uv.lock was generated on the VPS. Review and commit it before verification.\n'
