#!/usr/bin/env bash
set -euo pipefail

: "${TELEGRAM_BOT_TOKEN:?Set TELEGRAM_BOT_TOKEN}"
action=${1:-info}
api="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"

case "$action" in
  set)
    : "${WEBHOOK_URL:?Set WEBHOOK_URL to the public API origin}"
    : "${TELEGRAM_WEBHOOK_SECRET:?Set TELEGRAM_WEBHOOK_SECRET}"
    curl --fail --silent --show-error --request POST "$api/setWebhook" \
      --data-urlencode "url=${WEBHOOK_URL%/}/api/v1/telegram/webhook" \
      --data-urlencode "secret_token=${TELEGRAM_WEBHOOK_SECRET}" \
      --data-urlencode 'allowed_updates=["business_connection","business_message","edited_business_message","deleted_business_messages"]'
    ;;
  info)
    curl --fail --silent --show-error "$api/getWebhookInfo"
    ;;
  delete)
    curl --fail --silent --show-error --request POST "$api/deleteWebhook"
    ;;
  *)
    echo "usage: $0 {set|info|delete}" >&2
    exit 2
    ;;
esac

echo
