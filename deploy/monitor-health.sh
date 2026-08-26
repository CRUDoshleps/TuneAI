#!/bin/bash
set -Eeuo pipefail

readonly app_dir="/srv/apps/tuneai"
readonly env_file="$app_dir/deploy/.env.production"
readonly state_file="$app_dir/deploy/.deployed-tag"

fail() {
    echo "TuneAI monitoring failure: $*" >&2
    exit 1
}

[[ -r "$env_file" && -r "$state_file" ]] || fail "production environment or deployed-tag is missing"

set -a
# shellcheck source=/dev/null
source "$env_file"
set +a
: "${PUBLIC_HEALTH_URL:?PUBLIC_HEALTH_URL is required}"

readonly deployed_tag="$(tr -d '[:space:]' <"$state_file")"
[[ "$deployed_tag" =~ ^sha-([0-9a-f]{40})$ ]] || fail "invalid deployed tag"
readonly expected_revision="${BASH_REMATCH[1]}"
readonly readiness_url="${PUBLIC_HEALTH_URL%/health}/readiness"
readonly ai_readiness_url="${readiness_url}/ai"

readiness_body="$(curl --fail --silent --show-error --max-time 10 "$readiness_url")" || fail "public readiness endpoint is unavailable"
jq -e --arg revision "$expected_revision" \
    '.status == "ready" and .version == $revision' \
    <<<"$readiness_body" >/dev/null || fail "public readiness response does not match $expected_revision"

ai_body="$(curl --fail --silent --show-error --max-time 10 "$ai_readiness_url")" || fail "AI readiness endpoint is unavailable"
jq -e \
    '.status == "ready" and .configured == true and .mode == "real"' \
    <<<"$ai_body" >/dev/null || fail "production AI provider is not ready"

for service in rabbitmq backend worker frontend; do
    mapfile -t containers < <(
        docker ps -q \
            --filter label=com.docker.compose.project=tuneai \
            --filter "label=com.docker.compose.service=$service"
    )
    [[ "${#containers[@]}" -eq 1 ]] || fail "$service must have exactly one running container"
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${containers[0]}")"
    [[ "$status" == "healthy" ]] || fail "$service container status is $status"
done

systemctl is-active --quiet tuneai-deploy.timer || fail "deployment watcher timer is inactive"

disk_used="$(df -P / | awk 'NR == 2 {gsub(/%/, "", $5); print $5}')"
[[ "$disk_used" =~ ^[0-9]+$ ]] || fail "cannot determine root filesystem usage"
((disk_used < 90)) || fail "root filesystem usage is ${disk_used}%"

echo "TuneAI ${expected_revision} is ready; AI, containers, deployment watcher and disk are healthy (${disk_used}% used)."
