# Piklove — Telegram Business AI Copilot MVP

Privacy-first, multi-tenant reply copilot. It receives only official Telegram Business Bot updates, creates discovered conversations with **AI OFF**, and generates three replies only after the owner enables Copilot. **No user action = no outgoing AI message.**

## Architecture
See [architecture](docs/architecture.md), [threat model](docs/threat-model.md),
and the risk-first [product and engineering roadmap](docs/roadmap.md). The API
isolates Telegram, LLM and billing adapters. PostgreSQL is authoritative; Redis
is reserved for production debounce/rate-limit/locks. There is no userbot,
MTProto login, scraping, mass messaging or autopilot.

## Requirements and local setup
Docker 24+ and Compose v2, or Python 3.12, PostgreSQL 16, Redis 7 and Node 22.
```bash
cp .env.example .env
# fill secrets
docker compose up --build
```
API: `http://localhost:8000`; Mini App: `http://localhost:3000`.

## Environment
`.env.example` documents all settings. Bot/OpenAI/session secrets are backend-only. Model names are environment configuration. Never define `NEXT_PUBLIC_OPENAI_API_KEY`.

## Database migrations
Containers run `alembic upgrade head`; manually: `cd apps/api && alembic upgrade head`. Production startup never invokes `create_all` directly.

## Telegram Bot, Business and Mini App setup
Create a bot with BotFather, configure its Main Mini App URL, then add it as a Business Bot in the Telegram Business account and grant only intended chat/reply access. The SaaS cannot enumerate all private chats and only learns conversations delivered by Telegram. `/start` and the “Open app” menu are configured through BotFather/bot commands; a production HTTPS Mini App URL is required.

The implementation follows official Bot API update names `business_connection`, `business_message`, `edited_business_message`, and `deleted_business_messages`. `BusinessConnection.rights.can_reply` gates replies. Sending uses official `sendMessage` parameters `business_connection_id`, server-owned `chat_id`, and text. The requested live documentation verification could not be completed in this build environment because web access returned HTTP 401; verify against the current Bot API before deploying.

## Webhook setup
Expose API through HTTPS using Cloudflare Tunnel, ngrok, or another tunnel, then:
```bash
TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=... WEBHOOK_URL=https://example.test ./scripts/telegram-webhook.sh set
./scripts/telegram-webhook.sh info
./scripts/telegram-webhook.sh delete
```
Telegram's secret header is mandatory; obscurity is not authentication.

## OpenAI setup
Set the API key and all three model variables. The adapter uses the official Responses API structured parsing and `store=false` by default. Conversation text is untrusted input; the model has no Telegram, database, HTTP or filesystem tools and no recipient identifiers.

## Tests
```bash
cd apps/api
python -m pip install -e '.[dev]'
ruff check app tests
ruff format --check app tests
pytest
```

The suite includes deterministic Telegram/LLM fakes and covers Mini App auth,
privacy-safe logging, cross-tenant conversation denial, webhook idempotency and
the rule that `AI OFF` messages retain metadata without raw text.

## Privacy and retention
Telegram restrictions plus application ACL form two boundaries. AI OFF messages store metadata but no text. Copilot uses summary + allowlisted safe memory + the configured recent-message window. Cleanup nulls raw text after 30 days while retaining deduplication metadata. Users can erase per-conversation AI memory or all account data. Logs accept only identifiers/event metadata, never content.

## Known Telegram limitations
Bot API has no endpoint for all personal chats. Business access, reply capability and available updates are controlled by Telegram and the account's grants. Connecting the bot and provisioning HTTPS remain external setup. Telegram may reject sends after rights/reply-window changes; timeout outcomes are marked unknown rather than blindly retried.

## Current MVP limitations
Redis-backed debounce/rate limits, scheduled job runner, complete Telegram Stars invoice/pre-checkout activation, subscription cancellation, summary/memory extraction, CSRF double-submit protection and production metrics exporters are prepared architecturally but not wired end-to-end. Billing stays disabled. The UI supports the core connection/conversation/Copilot/suggestion/confirmed-send path; style/privacy controls need final mutation wiring. No autopilot exists or is feature-flagged.
