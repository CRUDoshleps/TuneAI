#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROJECT_NAME="${TUNEAI_MOODLE_PROJECT:-tuneai-moodle-e2e}"
COMPOSE=(docker compose -p "$PROJECT_NAME" -f "$ROOT_DIR/docker-compose.yml" -f "$ROOT_DIR/docker-compose.moodle.yml")
ENV_CREATED=0

cd "$ROOT_DIR"

cleanup() {
  local status=$?
  if [ "${KEEP_MOODLE_E2E:-0}" != "1" ]; then
    "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1 || true
  fi
  if [ "$ENV_CREATED" = "1" ]; then
    rm -f "$ROOT_DIR/.env"
  fi
  exit "$status"
}

wait_for_healthy() {
  local service="$1"
  local timeout="${2:-900}"
  local started
  started="$(date +%s)"
  while true; do
    local container
    container="$("${COMPOSE[@]}" ps -q "$service")"
    if [ -n "$container" ]; then
      local health
      health="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || true)"
      if [ "$health" = "healthy" ] || [ "$health" = "running" ]; then
        return 0
      fi
    fi
    if [ $(( $(date +%s) - started )) -ge "$timeout" ]; then
      "${COMPOSE[@]}" ps
      "${COMPOSE[@]}" logs --tail=160 "$service" || true
      return 1
    fi
    sleep 5
  done
}

trap cleanup EXIT

if [ ! -f "$ROOT_DIR/.env" ]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  ENV_CREATED=1
fi

if [ "${MOODLE_E2E_SKIP_BUILD:-0}" != "1" ]; then
  "${COMPOSE[@]}" up -d --build postgres rabbitmq backend worker moodle-postgres moodle
else
  "${COMPOSE[@]}" up -d postgres rabbitmq backend worker moodle-postgres moodle
fi
wait_for_healthy backend 240
wait_for_healthy worker 120
wait_for_healthy moodle 900

"${COMPOSE[@]}" exec -T moodle sh -lc "find /var/www/html/public/local/tuneai /tuneai-moodle-tests -name '*.php' -print0 | xargs -0 -n1 php -l"
"${COMPOSE[@]}" exec -T moodle php /var/www/html/admin/cli/purge_caches.php
"${COMPOSE[@]}" exec -T moodle php /var/www/html/admin/cli/upgrade.php --non-interactive --allow-unstable

"${COMPOSE[@]}" exec -T \
  -e TUNEAI_BASE_URL=http://backend:8000 \
  -e TUNEAI_MOODLE_KEY=tuneai-moodle-e2e-token \
  moodle php /tuneai-moodle-tests/tuneai_moodle_smoke.php
