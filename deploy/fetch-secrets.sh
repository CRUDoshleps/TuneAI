#!/bin/sh
set -eu
umask 077

runtime_dir="/run/apps/tuneai"
secret_name="tuneai-prod"
required_keys="secret_key postgres_password rabbitmq_password yandex_api_key bootstrap_admin_email bootstrap_admin_password"

install -d -m 0700 "$runtime_dir"
payload_file="$(mktemp "$runtime_dir/.payload.XXXXXX")"
trap 'rm -f "$payload_file"' EXIT

yc lockbox payload get "$secret_name" --format json >"$payload_file"
for key in $required_keys; do
    value="$(jq -er --arg key "$key" '.entries[] | select(.key == $key) | .text_value' "$payload_file")"
    target="$runtime_dir/$key"
    temporary="$runtime_dir/.$key.tmp"
    printf '%s' "$value" >"$temporary"
    chmod 0444 "$temporary"
    mv -f "$temporary" "$target"
done
