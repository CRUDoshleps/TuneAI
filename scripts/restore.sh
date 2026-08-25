#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <backup-directory>" >&2
  exit 2
fi

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="$1"
compose=(docker compose -f "$root_dir/docker-compose.yml")

test -r "$backup_dir/postgres.dump"
test -r "$backup_dir/uploads.tar.gz"

"${compose[@]}" up -d postgres
"${compose[@]}" exec -T postgres dropdb -U tuneai --if-exists tuneai
"${compose[@]}" exec -T postgres createdb -U tuneai tuneai
"${compose[@]}" exec -T postgres pg_restore -U tuneai -d tuneai --clean --if-exists < "$backup_dir/postgres.dump"
docker run --rm -v tuneai_uploads:/data -v "$backup_dir:/backup:ro" alpine:3.20 sh -c "cd /data && tar -xzf /backup/uploads.tar.gz"

echo "Restored $backup_dir"
