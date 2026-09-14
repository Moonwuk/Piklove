# Piklove — Telegram Business AI Copilot MVP

Privacy-first, multi-tenant reply copilot. It receives only official Telegram Business Bot updates,
creates discovered conversations with **AI OFF**, and generates three replies only after the owner
enables Copilot. **No user action = no outgoing AI message.**

## Architecture

See [architecture](docs/architecture.md) and [threat model](docs/threat-model.md). The API isolates
Telegram, LLM and billing adapters. PostgreSQL is authoritative; Redis is reserved for production
debounce/rate-limit/locks. There is no userbot, MTProto login, scraping, mass messaging or autopilot.

Delivery priorities and explicit non-goals are tracked in the [roadmap](docs/roadmap.md). The latest
closed-beta product findings are recorded in [the product review](docs/PRODUCT_REVIEW.md), and the
operator test is in [the beta checklist](docs/BETA_TESTING.md).

## Requirements and local setup

Docker 24+ and Compose v2, or Python 3.12, PostgreSQL 16, Redis 7 and Node 22.

```bash
cp .env.example .env
# fill secrets and URLs
docker compose up --build
```

API: `http://localhost:8000`; Mini App: `http://localhost:3000`.

For the repeatable closed-beta gate, use:

```bash
./scripts/beta-test.sh --live-ai
```

## Environment

`.env.example` documents all settings. Bot/OpenAI/session secrets are backend-only. Model names are
environment configuration. Never define `NEXT_PUBLIC_OPENAI_API_KEY`.

`NEXT_PUBLIC_API_URL` is intentionally public and is compiled into the web image. It must end with
`/api/v1` and must be reachable from the user's phone; a production image built with `localhost`
will call the phone itself rather than the server. `WEB_ORIGIN` is the exact Mini App origin allowed
by CORS.

## Database migrations

Containers run `alembic upgrade head`; manually: `cd apps/api && alembic upgrade head`. Production
startup never invokes `create_all` directly.

## Telegram Bot, Business and Mini App setup

Create a bot with BotFather, configure its Main Mini App HTTPS URL, then add it as a Business Bot in
the Telegram Business account and grant only intended chat/reply access. The SaaS cannot enumerate
all private chats and only learns conversations delivered by Telegram.

The implementation handles official Bot API updates `business_connection`, `business_message`,
`edited_business_message`, and `deleted_business_messages`. `BusinessConnection.rights.can_reply`
gates replies. Sending uses `sendMessage` with the server-owned `business_connection_id`, `chat_id`
and confirmed text.

## Webhook setup

Expose the API through HTTPS, set `WEBHOOK_URL` to its public origin, then:

```bash
./scripts/telegram-webhook.sh set
./scripts/telegram-webhook.sh info
./scripts/telegram-webhook.sh delete
```

Telegram's secret header is mandatory; obscurity is not authentication. The beta helper can register
the webhook only after all automated checks pass:

```bash
./scripts/beta-test.sh --live-ai --set-webhook
```

## OpenAI setup

Set the API key and all three model variables. The adapter uses the official Responses API structured
parsing and `store=false` by default. Conversation text is untrusted input; the model has no
Telegram, database, HTTP or filesystem tools and no recipient identifiers.

`OPENAI_TIMEOUT_SECONDS` and `OPENAI_MAX_RETRIES` bound every provider call. Missing credentials or
model names return `503 AI_PROVIDER_NOT_CONFIGURED`; upstream failures, timeouts and malformed
structured output return `502 AI_PROVIDER_UNAVAILABLE`. Provider error details are never returned to
the client.

## Quotas

Generation quotas are atomically reserved before any billable LLM call: `GET /api/v1/billing/usage`
returns `{plan, used, limit}`; the 21st generation on the default free plan returns HTTP 402 with
`{error: {code: "QUOTA_EXCEEDED", used, limit, plan}}`. Limits come from `FREE_GENERATIONS` /
`PRO_MONTHLY_GENERATIONS` and reset monthly. A reservation counts even if the provider later fails
because upstream cost may already have been incurred.

## Retention

Raw message text is dropped by an in-app background loop every
`RETENTION_SWEEP_INTERVAL_SECONDS` for messages older than `RAW_MESSAGE_RETENTION_DAYS`. This
enforces the privacy promise even without an external scheduler. A PostgreSQL advisory lock ensures
that only one API worker performs a sweep at a time.

## Verification

```bash
./scripts/verify.sh fast        # backend suite, web types, shell syntax
./scripts/verify.sh full        # fast + production web build + diff hygiene
./scripts/verify.sh postgres    # migration round-trip and PostgreSQL concurrency
./scripts/verify.sh containers  # Compose validation and production image builds
```

CI runs the backend tests on PostgreSQL, verifies Alembic upgrade/check/downgrade, typechecks and
builds the Mini App, validates every shell script, and builds both production containers.

## Privacy and retention

Telegram restrictions plus application ACL form two boundaries. AI OFF messages store metadata but
no text. Copilot uses summary + allowlisted safe memory + the configured recent-message window.
Cleanup nulls raw text after the configured retention window while retaining deduplication metadata.
Users can atomically erase all AI-derived memory or delete the entire account. Logs accept only
identifiers/event metadata, never content. SQLite enables foreign-key enforcement on every connection
so account erasure exercises the same `ON DELETE CASCADE` guarantee as PostgreSQL.

## Known Telegram limitations

Bot API has no endpoint for all personal chats. Business access, reply capability and available
updates are controlled by Telegram and the account's grants. Connecting the bot and provisioning
HTTPS remain external setup. Telegram may reject sends after rights/reply-window changes; timeout
outcomes are marked unknown rather than blindly retried. A repeated identical request uses the same
idempotency key and cannot create a second send.

## Current MVP limitations

Redis-backed rate limits/debounce, a dedicated external job runner, Telegram Stars billing,
subscription cancellation, summary/memory extraction, CSRF double-submit protection, pagination,
full browser E2E coverage and production metrics are not wired end-to-end. Billing stays disabled.
The closed beta is intentionally small and free. No autopilot exists or is feature-flagged.
