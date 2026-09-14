#!/usr/bin/env bash
# Build, start, and verify a Piklove beta environment with one command.
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
ENV_FILE="$ROOT/.env"
LIVE_AI=0
SET_WEBHOOK=0

usage() {
  cat <<'USAGE'
usage: ./scripts/beta-test.sh [--live-ai] [--set-webhook]

  --live-ai      make one synthetic request to the configured AI provider
  --set-webhook  register WEBHOOK_URL in Telegram after the smoke test passes
USAGE
}

for argument in "$@"; do
  case "$argument" in
    --live-ai) LIVE_AI=1 ;;
    --set-webhook) SET_WEBHOOK=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $argument" >&2; usage >&2; exit 2 ;;
  esac
done

for command in docker curl python3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
done

if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required (docker compose)." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE" >&2
  echo "Run: cp .env.example .env, then fill in the values." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required=(
  TELEGRAM_BOT_TOKEN
  TELEGRAM_WEBHOOK_SECRET
  OPENAI_API_KEY
  OPENAI_REPLY_MODEL
  OPENAI_ANALYSIS_MODEL
  OPENAI_SUMMARY_MODEL
  SESSION_SECRET
  WEB_ORIGIN
  NEXT_PUBLIC_API_URL
)
for name in "${required[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required value in $ENV_FILE: $name" >&2
    exit 1
  fi
done

if [[ "$TELEGRAM_WEBHOOK_SECRET" == "replace-with-random-secret" ]]; then
  echo "Replace the default TELEGRAM_WEBHOOK_SECRET before testing." >&2
  exit 1
fi
if [[ "$SESSION_SECRET" == "replace-with-32-random-bytes" || ${#SESSION_SECRET} -lt 32 ]]; then
  echo "SESSION_SECRET must be a random value of at least 32 characters." >&2
  exit 1
fi
if [[ "$NEXT_PUBLIC_API_URL" != */api/v1 ]]; then
  echo "NEXT_PUBLIC_API_URL must end with /api/v1." >&2
  exit 1
fi

if [[ "${ENVIRONMENT:-development}" == "production" ]]; then
  if [[ "$WEB_ORIGIN" != https://* || "$NEXT_PUBLIC_API_URL" != https://* ]]; then
    echo "Production WEB_ORIGIN and NEXT_PUBLIC_API_URL must use HTTPS." >&2
    exit 1
  fi
  if [[ "${COOKIE_SECURE:-false}" != "true" ]]; then
    echo "Production COOKIE_SECURE must be true." >&2
    exit 1
  fi
  if [[ "$NEXT_PUBLIC_API_URL" == *localhost* || "$NEXT_PUBLIC_API_URL" == *127.0.0.1* ]]; then
    echo "A phone cannot reach localhost in NEXT_PUBLIC_API_URL. Use the public API URL." >&2
    exit 1
  fi
fi

API_BASE=${BASE:-${NEXT_PUBLIC_API_URL%/api/v1}}
API_BASE=${API_BASE%/}
WEB_BASE=${WEB_BASE:-${WEB_ORIGIN%/}}

cd "$ROOT"
echo "1/5 Validating configuration..."
docker compose --env-file "$ENV_FILE" config >/dev/null
bash -n scripts/*.sh

echo "2/5 Building and starting Piklove..."
docker compose --env-file "$ENV_FILE" up -d --build

echo "3/5 Waiting for the API: $API_BASE"
api_ready=0
for _ in $(seq 1 60); do
  if curl --silent --fail --max-time 3 "$API_BASE/health/ready" >/dev/null 2>&1; then
    api_ready=1
    break
  fi
  sleep 2
done
if [[ "$api_ready" != "1" ]]; then
  echo "API did not become ready. Recent logs:" >&2
  docker compose --env-file "$ENV_FILE" logs --tail=120 api >&2
  exit 1
fi

echo "4/5 Waiting for the Mini App: $WEB_BASE"
web_ready=0
for _ in $(seq 1 60); do
  if curl --silent --fail --max-time 3 "$WEB_BASE" >/dev/null 2>&1; then
    web_ready=1
    break
  fi
  sleep 2
done
if [[ "$web_ready" != "1" ]]; then
  echo "Mini App did not become reachable. Recent logs:" >&2
  docker compose --env-file "$ENV_FILE" logs --tail=120 web >&2
  exit 1
fi

echo "5/5 Running the product smoke test..."
BASE="$API_BASE" \
SMOKE_LLM="$LIVE_AI" \
TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
TELEGRAM_WEBHOOK_SECRET="$TELEGRAM_WEBHOOK_SECRET" \
  "$ROOT/scripts/smoke-test.sh"

if [[ "$SET_WEBHOOK" == "1" ]]; then
  : "${WEBHOOK_URL:?Set WEBHOOK_URL to the public API origin before --set-webhook}"
  echo "Registering Telegram webhook..."
  TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
  TELEGRAM_WEBHOOK_SECRET="$TELEGRAM_WEBHOOK_SECRET" \
  WEBHOOK_URL="$WEBHOOK_URL" \
    "$ROOT/scripts/telegram-webhook.sh" set
  TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" \
    "$ROOT/scripts/telegram-webhook.sh" info
fi

echo
docker compose --env-file "$ENV_FILE" ps
echo
echo "Automated checks passed. Open the Mini App at: $WEB_ORIGIN"
echo "Manual beta checklist: docs/BETA_TESTING.md"
