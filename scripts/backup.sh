#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backup_dir="${BACKUP_DIR:-$root_dir/backups}"
stamp="$(date +%Y%m%d-%H%M%S)"
target="$backup_dir/tuneai-$stamp"
compose=(docker compose -f "$root_dir/docker-compose.yml")

mkdir -p "$target"

"${compose[@]}" exec -T postgres pg_dump -U tuneai -d tuneai -Fc > "$target/postgres.dump"
docker run --rm -v tuneai_uploads:/data/uploads:ro -v "$target:/backup" alpine:3.20 sh -c "cd /data && tar -czf /backup/uploads.tar.gz uploads"

cat > "$target/manifest.txt" <<EOF
created_at=$stamp
database=postgres.dump
uploads=uploads.tar.gz
EOF

echo "$target"
