#!/usr/bin/env bash
# Live smoke test against a running Piklove API (test credentials only).
set -euo pipefail
BASE=${BASE:-http://127.0.0.1:8001}
WHSEC=${WHSEC:-whsec-dev}
PASS=0; FAIL=0
ok()  { echo "PASS: $1"; PASS=$((PASS+1)); }
bad() { echo "FAIL: $1"; FAIL=$((FAIL+1)); }
hdr_secret="X-Telegram-Bot-Api-Secret-Token: $WHSEC"

tg_sig() { # $1 = tg_id
python3 - "$1" <<'PYEOF'
import hashlib, hmac, json, sys, time
from urllib.parse import urlencode
tg_id = int(sys.argv[1])
d = {"auth_date": str(int(time.time())), "query_id": "q",
     "user": json.dumps({"id": tg_id, "first_name": "Owner"}, separators=(",", ":"))}
check = "\n".join(f"{k}={v}" for k, v in sorted(d.items()))
secret = hmac.new(b"WebAppData", b"test-bot-token", hashlib.sha256).digest()
d["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
print(urlencode(d))
PYEOF
}

cookie=$(curl -s -D - -o /dev/null -X POST "$BASE/api/v1/auth/telegram" \
  -H 'Content-Type: application/json' \
  -d "{\"init_data\": \"$(tg_sig 100)\"}" | grep -i '^set-cookie' | sed 's/^[Ss]et-[Cc]ookie: //' | cut -d';' -f1)
[ -n "$cookie" ] && ok "auth: cookie issued" || bad "auth: no cookie"

# 1. webhook secret enforced
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/v1/telegram/webhook" \
  -H 'Content-Type: application/json' -d '{"update_id":1}')
[ "$code" = "401" ] && ok "webhook rejects missing secret (401)" || bad "webhook secret: got $code"

# 2. onboarding: connection event BEFORE first login
conn=$(printf '{"update_id":1,"business_connection":{"id":"conn-1","user":{"id":100,"first_name":"Owner"},"is_enabled":true,"rights":{"can_reply":true}}}')
code=$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/v1/telegram/webhook" \
  -H "$hdr_secret" -H 'Content-Type: application/json' -d "$conn")
[ "$code" = "200" ] && ok "webhook connection update accepted" || bad "connection update: $code"
status=$(curl -s "$BASE/api/v1/telegram/connection" -H "Cookie: $cookie" -b "$cookie")
echo "$status" | grep -q '"connected":true' && ok "connection visible after first login (onboarding fixed)" || bad "connection: $status"

# 3. privacy: message while AI OFF -> text discarded
msg1=$(printf '{"update_id":2,"business_message":{"business_connection_id":"conn-1","message_id":10,"date":%s,"chat":{"id":200,"type":"private","first_name":"Contact"},"from":{"id":200},"text":"super secret text"}}' "$(date +%s)")
curl -s -o /dev/null -X POST "$BASE/api/v1/telegram/webhook" -H "$hdr_secret" -H 'Content-Type: application/json' -d "$msg1"
conv_id=$(curl -s "$BASE/api/v1/conversations" -b "$cookie" | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')
detail=$(curl -s "$BASE/api/v1/conversations/$conv_id" -b "$cookie")
echo "$detail" | grep -q "super secret" && bad "PRIVACY LEAK: text retained while AI OFF" || ok "AI OFF: text discarded"

# 4. enable copilot -> next message retained
mode=$(curl -s -X PATCH "$BASE/api/v1/conversations/$conv_id/ai-mode" -b "$cookie" \
  -H 'Content-Type: application/json' -d '{"mode":"copilot"}')
echo "$mode" | grep -q '"ai_mode":"copilot"' && ok "copilot enabled" || bad "ai-mode: $mode"
msg2=$(printf '{"update_id":3,"business_message":{"business_connection_id":"conn-1","message_id":11,"date":%s,"chat":{"id":200,"type":"private","first_name":"Contact"},"from":{"id":200},"text":"please reply"}}' "$(date +%s)")
curl -s -o /dev/null -X POST "$BASE/api/v1/telegram/webhook" -H "$hdr_secret" -H 'Content-Type: application/json' -d "$msg2"
detail=$(curl -s "$BASE/api/v1/conversations/$conv_id" -b "$cookie")
echo "$detail" | grep -q "please reply" && ok "copilot ON: text retained" || bad "copilot retention failed"

# 5. quota: suggestions hit the real OpenAI client -> expect graceful failure (no api key),
#    but quota endpoint must work and count stays 0
usage=$(curl -s "$BASE/api/v1/billing/usage" -b "$cookie")
echo "$usage" | grep -q '"plan":"free"' && ok "usage endpoint: $usage" || bad "usage: $usage"

# 6. cross-user ACL
cookie_b=$(curl -s -D - -o /dev/null -X POST "$BASE/api/v1/auth/telegram" \
  -H 'Content-Type: application/json' \
  -d "{\"init_data\": \"$(tg_sig 999)\"}" | grep -i '^set-cookie' | sed 's/^[Ss]et-cookie: //I' | cut -d';' -f1)
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/conversations/$conv_id" -b "$cookie_b")
[ "$code" = "404" ] && ok "ACL: other user gets 404 on foreign conversation" || bad "ACL: got $code"

# 7. deleted account fails closed
cookie_c=$(curl -s -D - -o /dev/null -X POST "$BASE/api/v1/auth/telegram" \
  -H 'Content-Type: application/json' \
  -d "{\"init_data\": \"$(tg_sig 777)\"}" | grep -i '^set-cookie' | sed 's/^[Ss]et-cookie: //I' | cut -d';' -f1)
code=$(curl -s -o /dev/null -w '%{http_code}' -X DELETE "$BASE/api/v1/account/data" -b "$cookie_c")
[ "$code" = "204" ] && ok "account deletion: 204" || bad "delete: $code"
code=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/v1/auth/me" -b "$cookie_c")
[ "$code" = "401" ] && ok "deleted account session fails closed (401)" || bad "stale session: got $code"

echo "-----------------"
echo "PASS=$PASS FAIL=$FAIL"
[ "$FAIL" = "0" ]