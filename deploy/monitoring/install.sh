#!/bin/bash
set -Eeuo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this installer as root." >&2
    exit 1
fi

readonly source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly target_dir="/srv/monitoring"
readonly secret_file="$target_dir/secrets/grafana_admin_password"

install -d -o root -g root -m 0755 \
    "$target_dir" \
    "$target_dir/grafana/provisioning/datasources" \
    "$target_dir/grafana/provisioning/dashboards" \
    "$target_dir/grafana/dashboards"
install -d -o root -g root -m 0700 "$target_dir/secrets"

install -o root -g root -m 0644 "$source_dir/compose.yaml" "$target_dir/compose.yaml"
install -o root -g root -m 0644 "$source_dir/prometheus.yml" "$target_dir/prometheus.yml"
install -o root -g root -m 0644 "$source_dir/blackbox.yml" "$target_dir/blackbox.yml"
install -o root -g root -m 0644 \
    "$source_dir/grafana/provisioning/datasources/prometheus.yml" \
    "$target_dir/grafana/provisioning/datasources/prometheus.yml"
install -o root -g root -m 0644 \
    "$source_dir/grafana/provisioning/dashboards/default.yml" \
    "$target_dir/grafana/provisioning/dashboards/default.yml"
install -o root -g root -m 0644 \
    "$source_dir/grafana/dashboards/tuneai-overview.json" \
    "$target_dir/grafana/dashboards/tuneai-overview.json"

if [[ ! -s "$secret_file" ]]; then
    temporary_secret="$(mktemp "$target_dir/secrets/.grafana_admin_password.XXXXXX")"
    openssl rand -base64 24 | tr -d '\n' >"$temporary_secret"
    printf '\n' >>"$temporary_secret"
    chmod 0600 "$temporary_secret"
    mv -f -- "$temporary_secret" "$secret_file"
fi

docker compose --project-name tuneai-monitoring --file "$target_dir/compose.yaml" config --quiet
docker compose --project-name tuneai-monitoring --file "$target_dir/compose.yaml" up -d --remove-orphans

for attempt in {1..60}; do
    grafana_container="$(docker compose --project-name tuneai-monitoring --file "$target_dir/compose.yaml" ps -q grafana)"
    grafana_health=""
    if [[ -n "$grafana_container" ]]; then
        grafana_health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$grafana_container" 2>/dev/null || true)"
    fi
    [[ "$grafana_health" == "healthy" ]] && break
    if [[ "$attempt" == 60 ]]; then
        echo "Grafana did not become healthy." >&2
        exit 1
    fi
    sleep 2
done

docker compose --project-name tuneai-monitoring --file "$target_dir/compose.yaml" exec -T grafana \
    grafana cli admin reset-admin-password --password-from-stdin <"$secret_file" >/dev/null
echo "TuneAI Grafana and Prometheus are running."
