#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
  printf 'G6 preflight failed: %s\n' "$1" >&2
  exit 1
}

[[ "$(uname -s)" == "Linux" ]] || fail "Linux is required"
[[ "$(uname -m)" == "x86_64" ]] || fail "linux/amd64 is required"
grep -q '^VERSION_ID="24.04"$' /etc/os-release || fail "Ubuntu 24.04 is required"
git diff --quiet && git diff --cached --quiet || fail "working tree is not clean"
[[ -z "$(git status --porcelain)" ]] || fail "untracked files are present"

memory_kib="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
[[ "$memory_kib" -ge 3800000 ]] || fail "at least 4 GB class RAM is required"

read -r disk_kib disk_free_kib < <(df -Pk . | awk 'NR==2 {print $2, $4}')
[[ "$disk_kib" -ge 48000000 ]] || fail "at least 50 GB class disk is required"
[[ "$disk_free_kib" -ge 30000000 ]] || fail "at least 30 GB free is required"

inode_free="$(df -Pi . | awk 'NR==2 {print $4}')"
[[ "$inode_free" -ge 100000 ]] || fail "at least 100000 free inodes are required"

command -v docker >/dev/null || fail "Docker is required"
docker compose version >/dev/null || fail "Docker Compose v2 is required"

printf 'preflight=ok sha=%s\n' "$(git rev-parse HEAD)"
