#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 1 ]] || [[ ! "$1" =~ ^sha-([0-9a-f]{40})$ ]]; then
    echo "Usage: $0 sha-<40-hex-git-sha>" >&2
    exit 64
fi

readonly app_dir="/srv/apps/tuneai"
readonly compose_file="$app_dir/deploy/compose.yaml"
readonly env_file="$app_dir/deploy/.env.production"
readonly state_file="$app_dir/deploy/.deployed-tag"
readonly lock_file="/run/lock/tuneai-deploy.lock"
readonly new_tag="$1"
readonly expected_revision="${BASH_REMATCH[1]}"

exec 9>"$lock_file"
flock -n 9 || {
    echo "Another TuneAI deployment is already running." >&2
    exit 75
}

[[ -r "$compose_file" && -r "$env_file" ]] || {
    echo "TuneAI production Compose or environment file is missing." >&2
    exit 1
}

set -a
# shellcheck source=/dev/null
source "$env_file"
set +a
: "${REGISTRY_IMAGE:?REGISTRY_IMAGE is required}"
: "${PUBLIC_HEALTH_URL:?PUBLIC_HEALTH_URL is required}"

if [[ "$REGISTRY_IMAGE" != cr.yandex/*/tuneai ]]; then
    echo "REGISTRY_IMAGE must identify the TuneAI repository in cr.yandex." >&2
    exit 65
fi

previous_tag="$(cat "$state_file" 2>/dev/null || true)"
if [[ "$previous_tag" == "$new_tag" ]]; then
    echo "TuneAI $new_tag is already deployed."
    exit 0
fi

docker_config="$(mktemp -d /run/tuneai-docker.XXXXXX)"
cleanup() {
    rm -rf -- "$docker_config"
}
trap cleanup EXIT
export DOCKER_CONFIG="$docker_config"

"$app_dir/deploy/fetch-secrets.sh"
iam_token="$(
    curl --fail --silent --show-error \
        -H 'Metadata-Flavor: Google' \
        'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token' |
        jq -er '.access_token'
)"
printf '%s' "$iam_token" | docker login --username iam --password-stdin cr.yandex >/dev/null
unset iam_token

wait_containers_healthy() {
    local tag="$1"
    local deadline=$((SECONDS + 240))
    local service container status all_healthy

    while ((SECONDS < deadline)); do
        all_healthy=true
        for service in rabbitmq backend worker frontend; do
            container="$(IMAGE_TAG="$tag" docker compose --project-name tuneai --file "$compose_file" ps -q "$service")"
            if [[ -z "$container" ]]; then
                all_healthy=false
                break
            fi
            status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")"
            if [[ "$status" != "healthy" ]]; then
                all_healthy=false
                break
            fi
        done
        [[ "$all_healthy" == true ]] && return 0
        sleep 5
    done
    return 1
}

wait_external_health() {
    local revision="$1"
    local attempt body
    for attempt in {1..30}; do
        body="$(curl --fail --silent --show-error --max-time 5 "$PUBLIC_HEALTH_URL" || true)"
        if jq -e --arg revision "$revision" \
            '.status == "ok" and .version == $revision' <<<"$body" >/dev/null 2>&1
        then
            return 0
        fi
        sleep 3
    done
    return 1
}

rollback() {
    local exit_code=$?
    trap - ERR
    echo "Deployment failed; restoring the previous TuneAI image." >&2
    if [[ "$previous_tag" =~ ^(sha-)?[0-9a-f]{40}$ ]]; then
        IMAGE_TAG="$previous_tag" docker compose --project-name tuneai --file "$compose_file" up -d --remove-orphans || true
        wait_containers_healthy "$previous_tag" || true
    fi
    exit "$exit_code"
}
trap rollback ERR

IMAGE_TAG="$new_tag" docker compose --project-name tuneai --file "$compose_file" pull
IMAGE_TAG="$new_tag" docker compose --project-name tuneai --file "$compose_file" run --rm migrate
IMAGE_TAG="$new_tag" docker compose --project-name tuneai --file "$compose_file" run --rm bootstrap-admin
IMAGE_TAG="$new_tag" docker compose --project-name tuneai --file "$compose_file" up -d --remove-orphans
wait_containers_healthy "$new_tag"
wait_external_health "$expected_revision"

temporary_env="$(mktemp "$app_dir/deploy/.env.production.XXXXXX")"
awk -v tag="$new_tag" '
    BEGIN { found = 0 }
    /^IMAGE_TAG=/ { print "IMAGE_TAG=" tag; found = 1; next }
    { print }
    END { if (!found) print "IMAGE_TAG=" tag }
' "$env_file" >"$temporary_env"
chmod --reference="$env_file" "$temporary_env"
chown --reference="$env_file" "$temporary_env"
mv -f -- "$temporary_env" "$env_file"

temporary_state="$(mktemp "$app_dir/deploy/.deployed-tag.XXXXXX")"
printf '%s\n' "$new_tag" >"$temporary_state"
chmod 0644 "$temporary_state"
mv -f -- "$temporary_state" "$state_file"
trap - ERR
echo "TuneAI ${expected_revision} is healthy."
