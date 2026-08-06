#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
env_file="${1:-$root_dir/.env}"

if [ -e "$env_file" ]; then
  echo "$env_file already exists" >&2
  exit 1
fi

secret() {
  openssl rand -hex 32
}

password() {
  openssl rand -base64 24 | tr -d '=+/' | cut -c1-24
}

postgres_password="$(password)"
rabbitmq_password="$(password)"
minio_password="$(password)"
moodle_token="$(secret)"
secret_key="$(secret)"

sed \
  -e "s|^SECRET_KEY=.*|SECRET_KEY=$secret_key|" \
  -e "s|^MOODLE_INTEGRATION_ENABLED=.*|MOODLE_INTEGRATION_ENABLED=true|" \
  -e "s|^MOODLE_INTEGRATION_TOKEN=.*|MOODLE_INTEGRATION_TOKEN=$moodle_token|" \
  -e "s|^DEMO_BOOTSTRAP_ENABLED=.*|DEMO_BOOTSTRAP_ENABLED=false|" \
  -e "s|^YANDEX_MOCK=.*|YANDEX_MOCK=true|" \
  "$root_dir/.env.example" > "$env_file"

cat >> "$env_file" <<EOF
POSTGRES_PASSWORD=$postgres_password
RABBITMQ_PASSWORD=$rabbitmq_password
MINIO_ROOT_PASSWORD=$minio_password
EOF

echo "Created $env_file"
echo "Moodle integration token: $moodle_token"
