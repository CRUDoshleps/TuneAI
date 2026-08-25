#!/usr/bin/env bash
set -euo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
plugin_dir="$root_dir/integrations/moodle/local_tuneai"
out_dir="${1:-$root_dir/dist}"
archive="$out_dir/local_tuneai.zip"

mkdir -p "$out_dir"
rm -f "$archive"
cd "$plugin_dir/.."
zip -qr "$archive" local_tuneai -x "local_tuneai/.git/*" "local_tuneai/.DS_Store"
echo "$archive"
