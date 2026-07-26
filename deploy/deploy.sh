#!/bin/bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <immutable-image-tag>" >&2
    exit 2
fi

app_dir="/srv/apps/tuneai"
compose_file="$app_dir/deploy/compose.yaml"
env_file="$app_dir/deploy/.env.production"
state_file="$app_dir/deploy/.deployed-tag"
lock_file="/run/lock/tuneai-deploy.lock"
new_tag="$1"

exec 9>"$lock_file"
flock -n 9 || {
    echo "Another TuneAI deployment is already running." >&2
    exit 1
}

set -a
source "$env_file"
set +a
previous_tag="$(cat "$state_file" 2>/dev/null || true)"

compose() {
    IMAGE_TAG="$1" docker compose --project-name tuneai --file "$compose_file" "$@"
}

wait_healthy() {
    local tag="$1"
    local deadline=$((SECONDS + 180))
    local service container status
    while (( SECONDS < deadline )); do
        for service in rabbitmq backend worker frontend; do
            container="$(IMAGE_TAG="$tag" docker compose --project-name tuneai --file "$compose_file" ps -q "$service")"
            [[ -n "$container" ]] || return 1
            status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")"
            [[ "$status" == "healthy" ]] || break
        done
        [[ "$service" == "frontend" && "$status" == "healthy" ]] && return 0
        sleep 5
    done
    return 1
}

rollback() {
    local exit_code=$?
    if [[ -n "$previous_tag" ]]; then
        echo "Deployment failed; restoring image tag $previous_tag." >&2
        IMAGE_TAG="$previous_tag" docker compose --project-name tuneai --file "$compose_file" up -d --remove-orphans
        wait_healthy "$previous_tag" || true
    fi
    exit "$exit_code"
}
trap rollback ERR

IMAGE_TAG="$new_tag" docker compose --project-name tuneai --file "$compose_file" pull
IMAGE_TAG="$new_tag" docker compose --project-name tuneai --file "$compose_file" run --rm migrate
IMAGE_TAG="$new_tag" docker compose --project-name tuneai --file "$compose_file" run --rm bootstrap-admin
IMAGE_TAG="$new_tag" docker compose --project-name tuneai --file "$compose_file" up -d --remove-orphans
wait_healthy "$new_tag"

printf '%s\n' "$new_tag" >"$state_file"
trap - ERR
echo "TuneAI deployment $new_tag is healthy."
