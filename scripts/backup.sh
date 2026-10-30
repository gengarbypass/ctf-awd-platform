#!/usr/bin/env bash
set -euo pipefail
: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=awd}"
: "${PGUSER:=awd}"
: "${PGPASSWORD:?PGPASSWORD is required}"
export PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD
BACKUP_DIR="${BACKUP_DIR:-/data/awd/backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$BACKUP_DIR/awd-$STAMP.dump"
pg_dump --format=custom --no-owner --file="$FILE" "$PGDATABASE"
sha256sum "$FILE" > "$FILE.sha256"
if [[ -n "${OSS_BUCKET:-}" ]]; then
  command -v ossutil >/dev/null
  ossutil cp "$FILE" "oss://$OSS_BUCKET/database/$(basename "$FILE")"
  ossutil cp "$FILE.sha256" "oss://$OSS_BUCKET/database/$(basename "$FILE").sha256"
fi
printf '%s\n' "$FILE"
