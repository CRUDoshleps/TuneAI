#!/bin/sh
set -eu

read_secret() {
    variable_name="$1"
    secret_file="$2"
    if [ ! -r "$secret_file" ]; then
        echo "Required secret file is missing: $secret_file" >&2
        exit 1
    fi
    secret_value="$(cat "$secret_file")"
    export "$variable_name=$secret_value"
}

read_secret SECRET_KEY /run/secrets/secret_key
read_secret POSTGRES_PASSWORD /run/secrets/postgres_password
read_secret RABBITMQ_PASSWORD /run/secrets/rabbitmq_password

if [ -r /run/secrets/bootstrap_admin_email ]; then
    read_secret BOOTSTRAP_ADMIN_EMAIL /run/secrets/bootstrap_admin_email
fi
if [ -r /run/secrets/bootstrap_admin_password ]; then
    read_secret BOOTSTRAP_ADMIN_PASSWORD /run/secrets/bootstrap_admin_password
fi

export DATABASE_URL="postgresql+psycopg://tuneai:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:6432/tuneai?sslmode=verify-full&sslrootcert=/usr/local/share/ca-certificates/YandexInternalRootCA.crt"
export RABBITMQ_URL="amqp://tuneai:${RABBITMQ_PASSWORD}@rabbitmq:5672/"

exec "$@"
