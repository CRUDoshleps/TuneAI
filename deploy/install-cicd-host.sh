#!/bin/bash
set -euo pipefail

if [[ "$EUID" -ne 0 ]]; then
    echo "Run this provisioning step as root." >&2
    exit 1
fi

readonly source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

chmod 0755 \
    "$source_dir/deploy.sh" \
    "$source_dir/fetch-secrets.sh" \
    "$source_dir/monitor-health.sh" \
    "$source_dir/watch-registry.sh"
install -o root -g root -m 0644 "$source_dir/tuneai-deploy.service" /etc/systemd/system/tuneai-deploy.service
install -o root -g root -m 0644 "$source_dir/tuneai-deploy.timer" /etc/systemd/system/tuneai-deploy.timer
install -o root -g root -m 0644 "$source_dir/tuneai-health.service" /etc/systemd/system/tuneai-health.service
install -o root -g root -m 0644 "$source_dir/tuneai-health.timer" /etc/systemd/system/tuneai-health.timer

systemctl daemon-reload
systemctl enable --now tuneai-deploy.timer
systemctl enable --now tuneai-health.timer
systemctl start tuneai-health.service
echo "TuneAI registry watcher and health monitoring are enabled."
