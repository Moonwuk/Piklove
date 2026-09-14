# Piklove closed-beta test

This checklist is intentionally split into one automated command and a short real Telegram test.
The automated smoke test uses synthetic negative Telegram IDs, never sends a Telegram message, and
removes its test accounts when it finishes.

## 1. Prepare `.env`

```bash
cp .env.example .env
```

For a phone/Telegram test, use public HTTPS values:

```dotenv
ENVIRONMENT=production
WEB_ORIGIN=https://app.example.com
NEXT_PUBLIC_API_URL=https://api.example.com/api/v1
WEBHOOK_URL=https://api.example.com
COOKIE_SECURE=true
COOKIE_SAMESITE=lax
```

Fill all Telegram, OpenAI, model, database and session values. `NEXT_PUBLIC_API_URL` is compiled into
the browser bundle, so it must be reachable from the phone; `localhost` would point to the phone.
When the web and API origins are on unrelated sites, use `COOKIE_SAMESITE=none` with HTTPS.

## 2. Run the automated gate

```bash
./scripts/beta-test.sh --live-ai
```

This command validates the environment, builds and starts the containers, waits for the database,
and checks onboarding-before-login, authentication, Business connection state, AI-OFF privacy,
Copilot retention, input validation, a real synthetic AI generation, tenant isolation, memory
clearing and account deletion.

Register the production webhook only after the checks pass:

```bash
./scripts/beta-test.sh --live-ai --set-webhook
```

The webhook can also be managed separately:

```bash
./scripts/telegram-webhook.sh info
./scripts/telegram-webhook.sh set
./scripts/telegram-webhook.sh delete
```

## 3. Manual Telegram test

Use the Business account under test and a second Telegram account as the contact.

1. Open the Piklove Mini App inside Telegram. The home screen should show **connected**,
   **can reply**, and the current generation quota.
2. Keep Copilot off. From the second account, send a distinctive message. Open the new conversation;
   its existence should appear, but the text should say it was not retained.
3. Enable Copilot in that conversation. The screen must remain usable and retain the message list.
4. Send a new message from the second account. It should appear automatically within about five
   seconds without reopening the page.
5. Generate suggestions. Confirm that there are exactly three non-empty, sensible options.
6. Choose **Edit**, change the text, and send. The second account must receive exactly the edited
   text once.
7. Generate another set, then send a new incoming message before choosing an option. Piklove should
   reject the stale suggestion and ask for regeneration.
8. During one send, tap/retry only the same action. A slow or uncertain network result must not
   create a duplicate Telegram message.
9. Change several style sliders and fields, press **Save** once, reopen Settings, and confirm the
   values persisted.
10. Clear AI memory. Existing chat metadata should remain, while old generated suggestions become
    unusable.
11. Test account deletion last. The current session should stop working immediately.

## 4. Report format

Copy this block into the PR or test notes:

```text
Device / OS:
Telegram version:
Business account:
Web URL:
API URL:
Commit:

Automated beta-test: PASS / FAIL
Manual steps passed: 1 2 3 4 5 6 7 8 9 10 11
First failing step:
Expected:
Actual:
Screenshot or screen recording:
Request ID shown by the app/API (if present):
```

For a failure, collect only the relevant recent logs; do not publish `.env` or message content:

```bash
docker compose logs --since=10m --tail=200 api web
```
