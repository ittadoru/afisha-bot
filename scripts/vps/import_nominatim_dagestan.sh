#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

readonly source_url="${NOMINATIM_SOURCE_URL:-https://download.geofabrik.de/russia/north-caucasus-fed-district-latest.osm.pbf}"
readonly dagestan_relation_id="${DAGESTAN_OSM_RELATION_ID:-109876}"
readonly data_dir="$repo_root/var/nominatim"
readonly source_pbf="$data_dir/north-caucasus.osm.pbf"
readonly source_md5="$data_dir/north-caucasus.osm.pbf.md5"
readonly boundary_pbf="$data_dir/dagestan-boundary.osm.pbf"
readonly dagestan_pbf="$data_dir/dagestan.osm.pbf"
readonly ready_marker="$data_dir/.import-complete"
application_stopped=false

restore_application_on_error() {
  exit_code="$?"
  if [[ "$application_stopped" == true ]]; then
    printf 'Import failed; stopping the import container and restoring the application...\n' >&2
    docker compose --profile geo-import stop nominatim-import >/dev/null 2>&1 || true
    docker compose up --detach api bot frontend nginx >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}
trap restore_application_on_error ERR

for command_name in curl docker md5sum osmium; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf 'Missing required command: %s\n' "$command_name" >&2
    printf 'On Ubuntu install prerequisites with: apt-get update && apt-get install -y curl osmium-tool\n' >&2
    exit 1
  fi
done

if [[ -f "$ready_marker" ]]; then
  printf 'Nominatim was already imported. Refusing to run the one-time import again.\n' >&2
  exit 1
fi

if docker compose --profile geo-import run --rm --no-deps --entrypoint sh \
  nominatim-import -c 'find /var/lib/postgresql -name PG_VERSION -print -quit | grep -q .'; then
  printf 'The Nominatim volume already contains a database. Refusing to overwrite it.\n' >&2
  exit 1
fi

mkdir -p "$data_dir"

printf 'Downloading the North Caucasus extract...\n'
curl --fail --location --retry 3 --output "$source_pbf.part" "$source_url"
mv "$source_pbf.part" "$source_pbf"
curl --fail --location --retry 3 --output "$source_md5" "${source_url}.md5"

expected_md5="$(awk 'NR == 1 {print $1}' "$source_md5")"
actual_md5="$(md5sum "$source_pbf" | awk '{print $1}')"
if [[ -z "$expected_md5" || "$expected_md5" != "$actual_md5" ]]; then
  printf 'The downloaded PBF checksum does not match Geofabrik.\n' >&2
  exit 1
fi
osmium fileinfo --extended "$source_pbf" >/dev/null

printf 'Extracting the administrative boundary of Dagestan...\n'
osmium getid --add-referenced --overwrite \
  --output "$boundary_pbf" "$source_pbf" "r${dagestan_relation_id}"
osmium extract --strategy complete_ways --overwrite \
  --polygon "$boundary_pbf" --output "$dagestan_pbf" "$source_pbf"
osmium fileinfo --extended "$dagestan_pbf" >/dev/null

printf 'Stopping application services for the import...\n'
docker compose stop api bot worker beat frontend nginx nominatim 2>/dev/null || true
application_stopped=true

printf 'Starting the one-time Nominatim import...\n'
docker compose --profile geo-import up --detach nominatim-import

import_ready=false
for _ in $(seq 1 360); do
  if docker compose --profile geo-import exec -T nominatim-import \
    curl --fail --silent http://127.0.0.1:8080/status >/dev/null 2>&1; then
    import_ready=true
    break
  fi
  if ! docker compose --profile geo-import ps --status running --services \
    | grep -qx nominatim-import; then
    break
  fi
  sleep 30
done

if [[ "$import_ready" != true ]]; then
  printf 'Nominatim import did not become ready. Temporary files were kept for diagnosis.\n' >&2
  docker compose --profile geo-import logs --no-color --tail 120 nominatim-import >&2 || true
  exit 1
fi

docker compose --profile geo-import exec -T nominatim-import \
  sudo -u nominatim nominatim admin --project-dir /nominatim --check-database
docker compose --profile geo-import stop nominatim-import
docker compose --profile geo-import rm --force nominatim-import

printf 'Starting Nominatim and the application...\n'
docker compose --profile geo up --detach --wait \
  postgres redis migrate api bot frontend nginx nominatim

for coordinates in '42.9849,47.5047' '43.2509,46.5877' '42.0578,48.2888'; do
  latitude="${coordinates%,*}"
  longitude="${coordinates#*,}"
  docker compose --profile geo exec -T nominatim \
    curl --fail --silent \
    "http://127.0.0.1:8080/reverse?format=jsonv2&lat=${latitude}&lon=${longitude}" \
    >/dev/null
done

touch "$ready_marker"
rm -f "$source_pbf" "$source_md5" "$boundary_pbf" "$dagestan_pbf"
application_stopped=false
trap - ERR
printf 'Dagestan Nominatim import completed; temporary PBF files were removed.\n'
