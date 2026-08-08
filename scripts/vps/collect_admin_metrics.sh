#!/usr/bin/env bash
set -Eeuo pipefail

# Runs on demand from a systemd socket. The API receives only this read-only
# snapshot; it never receives the Docker socket or host /proc mount.
repo_root="$(git -C /opt/afishabot rev-parse --show-toplevel)"
output_dir="$repo_root/var/admin-metrics"
output_file="$output_dir/snapshot.json"
temporary_file="$output_dir/.snapshot.json.$$"
mkdir -p "$output_dir"
exec 9>"$output_dir/.collector.lock"
flock 9

disk_line="$(df -B1 --output=size,used,avail / | tail -n 1)"
read -r disk_size disk_used disk_available <<<"$disk_line"
memory_total="$(awk '/MemTotal:/ {print $2 * 1024}' /proc/meminfo)"
memory_available="$(awk '/MemAvailable:/ {print $2 * 1024}' /proc/meminfo)"
memory_used=$((memory_total - memory_available))
uptime_seconds="$(awk '{print int($1)}' /proc/uptime)"
read -r load_1 load_5 load_15 _ < /proc/loadavg

docker stats --no-stream --format '{{json .}}' | python3 -c '
import json, sys
items = []
for line in sys.stdin:
    row = json.loads(line)
    items.append({
        "name": row["Name"],
        "cpu_percent": float(row["CPUPerc"].rstrip("%")),
        "memory_usage": row["MemUsage"].split(" / ")[0],
        "memory_limit": row["MemUsage"].split(" / ")[1],
    })
print(json.dumps(items, ensure_ascii=False, separators=(",", ":")))
' > "$temporary_file.containers"

python3 - "$temporary_file" "$temporary_file.containers" \
  "$disk_size" "$disk_used" "$disk_available" "$memory_total" "$memory_used" \
  "$memory_available" "$uptime_seconds" "$load_1" "$load_5" "$load_15" <<'PY'
import json
import sys
from datetime import UTC, datetime

(output, containers_file, disk_size, disk_used, disk_available, memory_total,
 memory_used, memory_available, uptime, load_1, load_5, load_15) = sys.argv[1:]
with open(containers_file, encoding="utf-8") as source:
    containers = json.load(source)
payload = {
    "collected_at": datetime.now(UTC).isoformat(),
    "disk": {"size_bytes": int(disk_size), "used_bytes": int(disk_used), "available_bytes": int(disk_available)},
    "memory": {"total_bytes": int(memory_total), "used_bytes": int(memory_used), "available_bytes": int(memory_available)},
    "cpu": {"load_1": float(load_1), "load_5": float(load_5), "load_15": float(load_15)},
    "uptime_seconds": int(uptime),
    "containers": containers,
}
with open(output, "w", encoding="utf-8") as destination:
    json.dump(payload, destination, ensure_ascii=False, separators=(",", ":"))
PY
rm -f "$temporary_file.containers"
chmod 0644 "$temporary_file"
mv -f "$temporary_file" "$output_file"

if [[ "${1:-}" == "--stdout" ]]; then
  cat "$output_file"
fi
