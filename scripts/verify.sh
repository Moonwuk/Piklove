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

web_typecheck() {
  cd "$ROOT/apps/web"
  npm run typecheck
}

case "$MODE" in
  fast)
    backend
    web_typecheck
    ;;
  full)
    backend
    web_typecheck
    cd "$ROOT/apps/web"
    NEXT_TELEMETRY_DISABLED=1 npm run build
    cd "$ROOT"
    git diff --check
    ;;
  postgres)
    : "${TEST_DATABASE_URL:?set TEST_DATABASE_URL to a disposable PostgreSQL database}"
    : "${DATABASE_URL:?set DATABASE_URL to the same disposable PostgreSQL database}"
    cd "$ROOT/apps/api"
    alembic upgrade head
    alembic check
    python -m pytest tests/test_postgres_concurrency.py -q
    alembic downgrade base
    ;;
  live-llm)
    : "${LLM_API_KEY:?set LLM_API_KEY for the selected provider}"
    cd "$ROOT/apps/api"
    LLM_LIVE_TEST=1 python -m pytest tests/live/test_llm_contract.py -q
    ;;
  *)
    echo "usage: $0 {fast|full|postgres|live-llm}" >&2
    exit 2
    ;;
esac
