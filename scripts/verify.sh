#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
MODE=${1:-fast}

backend() {
  cd "$ROOT/apps/api"
  ruff check .
  ruff format --check .
  python -m pytest tests/ -q
}

web() {
  cd "$ROOT/apps/web"
  npm run typecheck
}

shell_scripts() {
  cd "$ROOT"
  bash -n scripts/*.sh
}

case "$MODE" in
  fast)
    backend
    web
    shell_scripts
    ;;
  full)
    backend
    web
    shell_scripts
    cd "$ROOT/apps/web"
    NEXT_TELEMETRY_DISABLED=1 npm run build
    cd "$ROOT"
    git diff --check
    ;;
  postgres)
    : "${TEST_DATABASE_URL:?Set TEST_DATABASE_URL to a disposable PostgreSQL database}"
    : "${DATABASE_URL:?Set DATABASE_URL to the same disposable PostgreSQL database}"
    cd "$ROOT/apps/api"
    alembic upgrade head
    alembic current --check-heads
    alembic check
    python -m pytest tests/test_postgres_concurrency.py -q
    alembic downgrade base
    ;;
  containers)
    cd "$ROOT"
    created_env=0
    if [[ ! -f .env ]]; then
      cp .env.example .env
      created_env=1
    fi
    cleanup() {
      if [[ "$created_env" == "1" ]]; then
        rm -f .env
      fi
    }
    trap cleanup EXIT
    docker compose config >/dev/null
    docker compose build
    ;;
  *)
    echo "usage: $0 {fast|full|postgres|containers}" >&2
    exit 2
    ;;
esac
