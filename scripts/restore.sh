#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "usage: restore.sh BACKUP.dump" >&2
  exit 2
fi
if [[ "${CONFIRM_RESTORE:-}" != "yes" ]]; then
  echo "set CONFIRM_RESTORE=yes after pausing the match and stopping API/Worker" >&2
  exit 2
fi
FILE="$1"
test -f "$FILE"
if [[ -f "$FILE.sha256" ]]; then
  sha256sum --check "$FILE.sha256"
fi
: "${PGHOST:=localhost}"
: "${PGPORT:=5432}"
: "${PGDATABASE:=awd}"
: "${PGUSER:=awd}"
: "${PGPASSWORD:?PGPASSWORD is required}"
export PGHOST PGPORT PGDATABASE PGUSER PGPASSWORD
pg_restore --clean --if-exists --no-owner --exit-on-error --dbname="$PGDATABASE" "$FILE"
