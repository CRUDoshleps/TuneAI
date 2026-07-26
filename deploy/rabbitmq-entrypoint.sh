#!/bin/sh
set -eu
umask 077

password="$(cat /run/secrets/rabbitmq_password)"
cat >/tmp/rabbitmq.conf <<EOF
default_user = tuneai
default_pass = ${password}
EOF
unset password

export RABBITMQ_CONFIG_FILE=/tmp/rabbitmq
exec docker-entrypoint.sh rabbitmq-server
