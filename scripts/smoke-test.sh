#!/usr/bin/env bash
# Non-destructive product smoke test against a running Piklove API.
# It uses synthetic negative Telegram IDs, never calls Telegram sendMessage,
# and removes the synthetic accounts before exiting.
set -euo pipefail

BASE=${BASE:-http://127.0.0.1:8000}
BASE=${BASE%/}
SMOKE_LLM=${SMOKE_LLM:-0}
: "${TELEGRAM_BOT_TOKEN:?Set TELEGRAM_BOT_TOKEN}"
: "${TELEGRAM_WEBHOOK_SECRET:?Set TELEGRAM_WEBHOOK_SECRET}"

TMP=$(mktemp -d)
BODY="$TMP/body.json"
OWNER_JAR="$TMP/owner.cookies"
OTHER_JAR="$TMP/other.cookies"
PASS=0
FAIL=0
OWNER_CREATED=0
OTHER_CREATED=0
seed=$(python3 - <<'PY'
import secrets
print(secrets.randbelow(800_000_000) + 100_000_000)
PY
)
owner_id="-$seed"
other_id="-$((seed + 1))"
chat_id="-$((seed + 2))"
connection_id="piklove-smoke-$seed"
update_id="-$seed"

ok() { echo "PASS: $1"; PASS=$((PASS + 1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL + 1)); }

request() {
  local method=$1 path=$2 data=${3:-} jar=${4:-} webhook_secret=${5:-0} idempotency_key=${6:-}
  local args=(--silent --show-error --connect-timeout 5 --max-time 45 --output "$BODY" --write-out '%{http_code}' --request "$method" "$BASE$path")
  [[ -n "$data" ]] && args+=(--header 'Content-Type: application/json' --data "$data")
  [[ -n "$jar" ]] && args+=(--cookie "$jar" --cookie-jar "$jar")
  [[ "$webhook_secret" == "1" ]] && args+=(--header "X-Telegram-Bot-Api-Secret-Token: $TELEGRAM_WEBHOOK_SECRET")
  [[ -n "$idempotency_key" ]] && args+=(--header "Idempotency-Key: $idempotency_key")
  HTTP_CODE=$(curl "${args[@]}")
}

sign_init_data() {
  TELEGRAM_BOT_TOKEN="$TELEGRAM_BOT_TOKEN" python3 - "$1" <<'PY'
import hashlib, hmac, json, os, sys, time
from urllib.parse import urlencode
telegram_id = int(sys.argv[1])
data = {
    "auth_date": str(int(time.time())),
    "query_id": f"piklove-smoke-{abs(telegram_id)}",
    "user": json.dumps({"id": telegram_id, "first_name": "Piklove Smoke"}, separators=(",", ":")),
}
check = "\n".join(f"{key}={value}" for key, value in sorted(data.items()))
secret = hmac.new(b"WebAppData", os.environ["TELEGRAM_BOT_TOKEN"].encode(), hashlib.sha256).digest()
data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
print(urlencode(data))
PY
}

authenticate() {
  local telegram_id=$1 jar=$2 init_data
  init_data=$(sign_init_data "$telegram_id")
  request POST /api/v1/auth/telegram "$(python3 - "$init_data" <<'PY'
import json, sys
print(json.dumps({"init_data": sys.argv[1]}))
PY
)" "$jar"
}

cleanup() {
  set +e
  [[ "$OWNER_CREATED" == "1" && -f "$OWNER_JAR" ]] && curl --silent --max-time 10 --request DELETE --cookie "$OWNER_JAR" "$BASE/api/v1/account/data" >/dev/null
  [[ "$OTHER_CREATED" == "1" && -f "$OTHER_JAR" ]] && curl --silent --max-time 10 --request DELETE --cookie "$OTHER_JAR" "$BASE/api/v1/account/data" >/dev/null
  rm -rf "$TMP"
}
trap cleanup EXIT

echo "Piklove product smoke test: $BASE"
echo "Synthetic owner ID: $owner_id"
echo

request GET /health/live
if [[ "$HTTP_CODE" == "200" ]] && grep -q '"status":"ok"' "$BODY"; then ok "API liveness"; else bad "API liveness (HTTP $HTTP_CODE: $(cat "$BODY"))"; fi
request GET /health/ready
if [[ "$HTTP_CODE" == "200" ]] && grep -q '"status":"ready"' "$BODY"; then ok "database readiness"; else bad "database readiness (HTTP $HTTP_CODE: $(cat "$BODY"))"; fi
request POST /api/v1/telegram/webhook '{"update_id":-1}'
if [[ "$HTTP_CODE" == "401" ]]; then ok "webhook rejects a missing secret"; else bad "webhook secret enforcement (HTTP $HTTP_CODE)"; fi

connection_payload=$(printf '{"update_id":%s,"business_connection":{"id":"%s","user":{"id":%s,"first_name":"Piklove Smoke"},"is_enabled":true,"rights":{"can_reply":true}}}' "$update_id" "$connection_id" "$owner_id")
request POST /api/v1/telegram/webhook "$connection_payload" "" 1
if [[ "$HTTP_CODE" == "200" ]]; then ok "Business connection accepted before first Mini App login"; else bad "Business connection webhook (HTTP $HTTP_CODE: $(cat "$BODY"))"; fi

if authenticate "$owner_id" "$OWNER_JAR" && [[ "$HTTP_CODE" == "200" ]]; then OWNER_CREATED=1; ok "Telegram Mini App authentication"; else bad "Telegram Mini App authentication (HTTP ${HTTP_CODE:-curl-error})"; fi
request GET /api/v1/telegram/connection "" "$OWNER_JAR"
if [[ "$HTTP_CODE" == "200" ]] && python3 - "$BODY" <<'PY'
import json, sys
value = json.load(open(sys.argv[1]))
raise SystemExit(0 if value == {"connected": True, "can_reply": True} else 1)
PY
then ok "connection is visible and can reply"; else bad "connection state (HTTP $HTTP_CODE: $(cat "$BODY"))"; fi
request GET /api/v1/settings/style "" "$OWNER_JAR"
if [[ "$HTTP_CODE" == "200" ]] && python3 - "$BODY" <<'PY'
import json, sys
raise SystemExit(0 if json.load(open(sys.argv[1])).get("tone") == "natural" else 1)
PY
then ok "style defaults are provisioned"; else bad "style defaults (HTTP $HTTP_CODE: $(cat "$BODY"))"; fi
request GET /api/v1/billing/subscription "" "$OWNER_JAR"
if [[ "$HTTP_CODE" == "200" ]] && grep -q '"plan":"free"' "$BODY"; then ok "free subscription is provisioned"; else bad "subscription bootstrap (HTTP $HTTP_CODE: $(cat "$BODY"))"; fi

now=$(date +%s)
off_text="Piklove smoke private text $seed"
message_off=$(printf '{"update_id":%s,"business_message":{"business_connection_id":"%s","message_id":10,"date":%s,"chat":{"id":%s,"type":"private","first_name":"Smoke Contact"},"from":{"id":%s},"text":"%s"}}' "$((update_id - 1))" "$connection_id" "$now" "$chat_id" "$chat_id" "$off_text")
request POST /api/v1/telegram/webhook "$message_off" "" 1
if [[ "$HTTP_CODE" == "200" ]]; then ok "message is accepted while Copilot is off"; else bad "AI-off message webhook (HTTP $HTTP_CODE)"; fi
request GET /api/v1/conversations "" "$OWNER_JAR"
conversation_id=""
[[ "$HTTP_CODE" == "200" ]] && conversation_id=$(python3 - "$BODY" <<'PY'
import json, sys
rows = json.load(open(sys.argv[1])); print(rows[0]["id"] if rows else "")
PY
)
if [[ -n "$conversation_id" ]]; then ok "conversation is discovered"; else bad "conversation discovery (HTTP $HTTP_CODE: $(cat "$BODY"))"; fi

if [[ -n "$conversation_id" ]]; then
  request GET "/api/v1/conversations/$conversation_id" "" "$OWNER_JAR"
  if [[ "$HTTP_CODE" == "200" ]] && python3 - "$BODY" "$off_text" <<'PY'
import json, sys
texts = [item.get("text") for item in json.load(open(sys.argv[1])).get("messages", [])]
raise SystemExit(0 if sys.argv[2] not in [text for text in texts if text] else 1)
PY
  then ok "AI OFF discards message text"; else bad "AI OFF privacy invariant"; fi

  request PATCH "/api/v1/conversations/$conversation_id/ai-mode" '{"mode":"copilot"}' "$OWNER_JAR"
  if [[ "$HTTP_CODE" == "200" ]] && grep -q '"ai_mode":"copilot"' "$BODY"; then ok "Copilot can be enabled"; else bad "enable Copilot (HTTP $HTTP_CODE)"; fi

  on_text="Piklove smoke retained text $seed"
  message_on=$(printf '{"update_id":%s,"business_message":{"business_connection_id":"%s","message_id":11,"date":%s,"chat":{"id":%s,"type":"private","first_name":"Smoke Contact"},"from":{"id":%s},"text":"%s"}}' "$((update_id - 2))" "$connection_id" "$((now + 1))" "$chat_id" "$chat_id" "$on_text")
  request POST /api/v1/telegram/webhook "$message_on" "" 1
  request GET "/api/v1/conversations/$conversation_id" "" "$OWNER_JAR"
  if [[ "$HTTP_CODE" == "200" ]] && python3 - "$BODY" "$on_text" <<'PY'
import json, sys
texts = [item.get("text") for item in json.load(open(sys.argv[1])).get("messages", [])]
raise SystemExit(0 if sys.argv[2] in texts else 1)
PY
  then ok "Copilot retains new message text"; else bad "Copilot retention"; fi

  request POST "/api/v1/conversations/$conversation_id/send-custom" '{"generation_id":"not-used","text":"   "}' "$OWNER_JAR" 0 "smoke-empty-$seed"
  if [[ "$HTTP_CODE" == "422" ]]; then ok "blank edited replies are rejected"; else bad "blank edited reply validation (HTTP $HTTP_CODE)"; fi

  if [[ "$SMOKE_LLM" == "1" ]]; then
    request POST "/api/v1/conversations/$conversation_id/suggestions" "" "$OWNER_JAR"
    if [[ "$HTTP_CODE" == "200" ]] && python3 - "$BODY" <<'PY'
import json, sys
value = json.load(open(sys.argv[1])); raise SystemExit(0 if value.get("generation_id") and len(value.get("options", [])) == 3 else 1)
PY
    then ok "configured AI provider returns three validated suggestions"; else bad "live AI generation (HTTP $HTTP_CODE: $(cat "$BODY"))"; fi
  else
    echo "SKIP: live AI generation (run beta-test.sh --live-ai to include it)"
  fi

  request DELETE /api/v1/account/memory "" "$OWNER_JAR"
  if [[ "$HTTP_CODE" == "204" ]]; then ok "all AI memory clears atomically"; else bad "AI-memory erasure (HTTP $HTTP_CODE)"; fi
fi

if authenticate "$other_id" "$OTHER_JAR" && [[ "$HTTP_CODE" == "200" ]]; then
  OTHER_CREATED=1
  if [[ -n "$conversation_id" ]]; then
    request GET "/api/v1/conversations/$conversation_id" "" "$OTHER_JAR"
    if [[ "$HTTP_CODE" == "404" ]]; then ok "another account cannot read the conversation"; else bad "tenant isolation (HTTP $HTTP_CODE)"; fi
  fi
else bad "second-account authentication"; fi

if [[ "$OWNER_CREATED" == "1" ]]; then
  request DELETE /api/v1/account/data "" "$OWNER_JAR"
  if [[ "$HTTP_CODE" == "204" ]]; then
    OWNER_CREATED=0; ok "account data deletion"
    request GET /api/v1/auth/me "" "$OWNER_JAR"
    if [[ "$HTTP_CODE" == "401" ]]; then ok "deleted account session fails closed"; else bad "deleted session invalidation (HTTP $HTTP_CODE)"; fi
  else bad "account deletion (HTTP $HTTP_CODE)"; fi
fi
if [[ "$OTHER_CREATED" == "1" ]]; then request DELETE /api/v1/account/data "" "$OTHER_JAR"; [[ "$HTTP_CODE" == "204" ]] && OTHER_CREATED=0; fi

echo
echo "-----------------------------"
echo "PASS=$PASS FAIL=$FAIL"
[[ "$FAIL" == "0" ]]
