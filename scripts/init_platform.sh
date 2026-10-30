#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"
if [[ ! -f .env ]]; then
  echo "backend/.env is required; copy .env.example and inject secrets first" >&2
  exit 1
fi
set -a
source .env
set +a
alembic upgrade head
python "$ROOT/scripts/seed.py"
