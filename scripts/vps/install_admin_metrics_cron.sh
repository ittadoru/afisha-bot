#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$(id -u)" -eq 0 ]] || { printf 'Run as root.\n' >&2; exit 1; }
repo_root="$(git rev-parse --show-toplevel)"
collector="$repo_root/scripts/vps/collect_admin_metrics.sh"
cron_file="/etc/cron.d/afishabot-admin-metrics"

chmod 0755 "$collector"
"$collector"
printf '%s\n' \
  'SHELL=/bin/bash' \
  'PATH=/usr/sbin:/usr/bin:/sbin:/bin' \
  "* * * * * root $collector" > "$cron_file"
chmod 0644 "$cron_file"
systemctl reload cron || systemctl restart cron
printf 'Admin metrics collector installed: %s\n' "$cron_file"
