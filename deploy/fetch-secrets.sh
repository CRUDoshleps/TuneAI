#!/bin/bash
set -euo pipefail
umask 077

runtime_dir="/run/apps/tuneai"
required_keys="secret_key postgres_password rabbitmq_password yandex_api_key bootstrap_admin_email bootstrap_admin_password"
: "${LOCKBOX_SECRET_ID:?LOCKBOX_SECRET_ID is required}"

install -d -m 0700 "$runtime_dir"
payload_file="$(mktemp "$runtime_dir/.payload.XXXXXX")"
trap 'rm -f "$payload_file"' EXIT

token="$({
    curl -fsS \
        -H 'Metadata-Flavor: Google' \
        'http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token'
} | jq -er '.access_token')"

curl -fsS \
    -H "Authorization: Bearer $token" \
    "https://payload.lockbox.api.cloud.yandex.net/lockbox/v1/secrets/${LOCKBOX_SECRET_ID}/payload" \
    >"$payload_file"

for key in $required_keys; do
    value="$(jq -er --arg key "$key" '.entries[] | select(.key == $key) | .textValue' "$payload_file")"
    target="$runtime_dir/$key"
    temporary="$runtime_dir/.$key.tmp"
    printf '%s' "$value" >"$temporary"
    chmod 0444 "$temporary"
    mv -f "$temporary" "$target"
done
