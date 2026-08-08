#!/usr/bin/env bash
set -Eeuo pipefail

[[ "$(id -u)" -eq 0 ]] || { printf 'Run as root.\n' >&2; exit 1; }
repo_root="$(git rev-parse --show-toplevel)"
collector="$repo_root/scripts/vps/collect_admin_metrics.sh"
unit_dir="$repo_root/scripts/vps/systemd"

install -d -m 0755 "$repo_root/var/admin-metrics"
chmod 0755 "$collector"
install -m 0644 "$unit_dir/afishabot-admin-metrics.socket" /etc/systemd/system/
install -m 0644 "$unit_dir/afishabot-admin-metrics@.service" /etc/systemd/system/
rm -f /etc/cron.d/afishabot-admin-metrics
systemctl daemon-reload
systemctl enable --now afishabot-admin-metrics.socket
"$collector"
printf 'Admin metrics socket installed.\n'
