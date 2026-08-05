#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

fail() {
  printf 'Stage A verification failed: %s\n' "$1" >&2
  exit 1
}

bash scripts/vps/preflight.sh

[[ "$(git rev-parse HEAD)" == "$(git rev-parse origin/main)" ]] || \
  fail "HEAD does not match origin/main"
[[ "$(stat -c '%U:%G %a' .env)" == "root:root 600" ]] || \
  fail ".env must be root:root mode 600"

expected_services=$'api\nbot\nfrontend\nnginx\npostgres\nredis'
running_services="$(docker compose ps --services --filter status=running | sort)"
[[ "$running_services" == "$expected_services" ]] || {
  printf 'Expected running services:\n%s\nActual:\n%s\n' \
    "$expected_services" "$running_services" >&2
  exit 1
}

for forbidden in nominatim nominatim-import prometheus alertmanager node-exporter; do
  if docker compose ps --services --filter status=running | grep -qx "$forbidden"; then
    fail "forbidden Stage A service is running: $forbidden"
  fi
done

for port in 5432 6379 9090 9093 9100; do
  if ss -lntH "sport = :$port" | grep -q .; then
    fail "private service port is listening on the host: $port"
  fi
done

redirect="$(curl --silent --output /dev/null --write-out '%{http_code} %{redirect_url}' \
  http://podvval.xyz/)"
[[ "$redirect" == "301 https://podvval.xyz/" ]] || \
  fail "unexpected HTTP redirect: $redirect"

for path in / /app; do
  status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
    "https://podvval.xyz${path}")"
  [[ "$status" == "200" ]] || fail "${path} returned $status"
done

metrics_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  https://podvval.xyz/metrics)"
[[ "$metrics_status" == "404" ]] || fail "/metrics returned $metrics_status"

admin_status="$(curl --silent --output /dev/null --write-out '%{http_code}' \
  https://admin.podvval.xyz/)"
[[ "$admin_status" == "404" ]] || fail "admin root returned $admin_status"

certificate="$(openssl s_client -connect podvval.xyz:443 -servername podvval.xyz \
  </dev/null 2>/dev/null | openssl x509 -noout -ext subjectAltName)"
grep -q 'DNS:podvval.xyz' <<<"$certificate" || fail "certificate misses podvval.xyz"
grep -q 'DNS:admin.podvval.xyz' <<<"$certificate" || \
  fail "certificate misses admin.podvval.xyz"

printf 'stage_a=ok sha=%s\n' "$(git rev-parse HEAD)"
