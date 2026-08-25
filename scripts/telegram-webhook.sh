#!/usr/bin/env bash
set -euo pipefail
: "${TELEGRAM_BOT_TOKEN:?}"; action="${1:-info}"; api="https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}"
case "$action" in set) : "${WEBHOOK_URL:?}"; : "${TELEGRAM_WEBHOOK_SECRET:?}"; curl -fsS "$api/setWebhook" -d "url=${WEBHOOK_URL%/}/api/v1/telegram/webhook" -d "secret_token=$TELEGRAM_WEBHOOK_SECRET" -d 'allowed_updates=["business_connection","business_message","edited_business_message","deleted_business_messages","pre_checkout_query","message"]';; info) curl -fsS "$api/getWebhookInfo";; delete) curl -fsS "$api/deleteWebhook";; *) echo 'set|info|delete' >&2;exit 2;;esac
