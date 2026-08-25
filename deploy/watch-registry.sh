#!/bin/bash
set -euo pipefail

readonly app_dir="/srv/apps/tuneai"
readonly env_file="$app_dir/deploy/.env.production"

[[ -r "$env_file" ]] || {
    echo "Missing $env_file" >&2
    exit 1
}

set -a
# shellcheck source=/dev/null
source "$env_file"
set +a
: "${REGISTRY_IMAGE:?REGISTRY_IMAGE is required}"

if [[ ! "$REGISTRY_IMAGE" =~ ^cr\.yandex/([a-z0-9]{20})/tuneai$ ]]; then
    echo "REGISTRY_IMAGE must match cr.yandex/<registry-id>/tuneai." >&2
    exit 65
fi
readonly registry_id="${BASH_REMATCH[1]}"

token="$(
    curl --fail --silent --show-error \
        -H 'Metadata-Flavor: Google' \
        'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token' |
        jq -er '.access_token'
)"

list_images() {
    local repository="$1"
    curl --fail --silent --show-error --get \
        -H "Authorization: Bearer $token" \
        --data-urlencode "repositoryName=${registry_id}/tuneai/${repository}" \
        --data-urlencode "pageSize=100" \
        'https://container-registry.api.cloud.yandex.net/container-registry/v1/images'
}

backend_payload="$(list_images backend)"
frontend_payload="$(list_images frontend)"
unset token

tag="$(
    jq -er --argjson frontend "$frontend_payload" '
        [$frontend.images[]? | .tags[]?] as $frontend_tags
        | [.images[]? as $image
           | $image.tags[]?
           | select(test("^sha-[0-9a-f]{40}$"))
           | select(. as $tag | $frontend_tags | index($tag))
           | {tag: ., createdAt: $image.createdAt}]
        | sort_by(.createdAt)
        | (last // empty)
        | .tag
    ' <<<"$backend_payload" 2>/dev/null || true
)"

if [[ ! "$tag" =~ ^sha-[0-9a-f]{40}$ ]]; then
    echo "No complete immutable TuneAI release is available yet."
    exit 0
fi

exec "$app_dir/deploy/deploy.sh" "$tag"
