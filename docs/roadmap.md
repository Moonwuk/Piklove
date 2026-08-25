# Product and Engineering Roadmap

## 1. Purpose

This roadmap turns the current prototype into a production-oriented Telegram
Business AI Copilot. The ordering is risk-first: privacy, tenant isolation and
the explicit-send invariant are completed before billing, growth or advanced AI
memory.

The product invariant for every milestone is:

> **No explicit authenticated user action = no outgoing AI message.**

There is no autopilot milestone. The product remains a reply copilot for chats
made available through the official Telegram Business Bot API.

## 2. Current baseline

The repository currently provides:

- a FastAPI and async SQLAlchemy application skeleton;
- Telegram Mini App `initData` authentication;
- Telegram Business webhook handling and secret verification;
- conversations created with `AI OFF` by default;
- structured conversation analysis and three reply suggestions;
- a second ACL check and server-side recipient resolution before sending;
- a minimal Next.js Mini App;
- PostgreSQL, Redis and Docker Compose definitions;
- initial architecture, threat-model and privacy documentation.

The baseline is not yet production-ready. In particular, the critical test
matrix, Redis controls, background jobs, full billing flow, frontend mutations,
operational telemetry and deployment hardening remain incomplete.

## 3. Prioritization rules

Work is selected in this order:

1. **Prevent privacy or recipient mistakes.**
2. **Make the core flow deterministic and testable.**
3. **Make local and staging deployment reproducible.**
4. **Make the UX complete enough for a closed beta.**
5. **Add monetization only after usage accounting is trustworthy.**
6. **Add memory and summaries only after retention controls are proven.**

Every milestone must include tests, migration review, privacy review and updated
documentation. A milestone is not complete when its happy path alone works.

## 4. Milestone 0 — Stabilize the foundation

**Target:** one engineering iteration.

**Status:** in progress. The first stabilization increment reformatted the
backend, removed wildcard imports, enabled stricter lint rules, introduced
FastAPI dependency-injection seams for Telegram and LLM providers, and added
deterministic external-service fakes plus initial tenant/privacy integration
tests. Explicit Alembic operations, repository extraction, lock files and CI
remain before this milestone can pass its exit criteria.

### Deliverables

- Reformat the compressed prototype code into maintainable typed modules.
- Replace wildcard imports and broad exception handling.
- Introduce repository classes with mandatory `user_id` predicates.
- Replace the metadata-driven initial migration with explicit Alembic operations.
- Add a single typed API error model and domain error mapping.
- Add dependency-injection seams for Telegram, LLM, clock and Redis adapters.
- Add local test settings and isolated PostgreSQL-compatible test fixtures.
- Pin runtime and development dependencies with a reproducible lock file.
- Validate Dockerfiles and Compose startup, including migrations and healthchecks.

### Exit criteria

- `ruff`, type checking, backend tests and frontend checks pass in CI.
- A clean database can be created exclusively with `alembic upgrade head`.
- API startup never creates schema objects directly.
- No production service constructs a concrete external gateway inside route code.
- The repository can be started from the README on a clean machine.

## 5. Milestone 1 — Privacy and tenant-isolation gate

**Target:** one engineering iteration.

### Deliverables

- Enforce tenant ownership in repositories for conversations, messages,
  generations, memories, subscriptions, usage and send attempts.
- Make webhook message deduplication transactional.
- Ensure `AI OFF` persists no message text, captions or unsupported content.
- Add early-drop behavior for unknown, disabled or revoked business connections.
- Implement CSRF protection for cookie-authenticated mutations.
- Implement tenant-aware Redis rate limits for auth, suggestions and sends.
- Add privacy-safe structured logging with automated field allowlisting.
- Add account deletion and memory deletion integration tests.
- Document the data inventory and retention purpose for every stored field.

### Required tests

- User A cannot list, read, mutate or send from User B's conversation.
- User A cannot use User B's generation or business connection.
- `AI OFF` cannot generate and does not retain raw content.
- Switching Copilot off after generation rejects sending.
- Duplicate Telegram updates create one message.
- Edited and deleted messages are reflected and excluded from AI context.
- Raw content cannot enter logs, analytics or exception payloads.

### Exit criteria

- The complete security test matrix passes against PostgreSQL.
- Privacy review finds no route that loads tenant data by entity ID alone.
- A revoked connection blocks sends before the Telegram call.
- The threat model matches the implemented controls.

## 6. Milestone 2 — Reliable Telegram Business core flow

**Target:** one engineering iteration.

### Deliverables

- Verify all Telegram Business fields and update types against the current
  official Bot API documentation and capture the supported Bot API version.
- Add typed Pydantic schemas for supported webhook payloads.
- Reconcile `business_connection` state with `getBusinessConnection` where safe.
- Correctly classify incoming and owner-sent outgoing business messages.
- Implement durable send reservations and idempotency-key replay responses.
- Model `pending`, `sent`, `failed` and `unknown` send outcomes explicitly.
- Map Telegram 400/403/429/5xx and timeout failures to stable domain errors.
- Never blindly retry a send with an unknown result.
- Add `/start` onboarding with an official Mini App button.
- Add webhook setup and diagnostics commands without exposing secrets.

### Exit criteria

- The mocked end-to-end integration flow passes:
  connection → first message → `AI OFF` → enable Copilot → retained message →
  three suggestions → select option 2 → exact Business `sendMessage` request.
- The asserted Telegram call contains the database-owned
  `business_connection_id`, `chat_id` and selected text.
- Duplicate send requests do not produce duplicate Telegram calls.
- Revoke, rate-limit, unavailable-chat and timeout paths have deterministic UI
  errors and persisted send states.

## 7. Milestone 3 — AI pipeline, debounce and usage controls

**Target:** one to two engineering iterations.

### Deliverables

- Implement Redis debounce with a versioned conversation key and four-second
  configurable quiet window.
- Persist messages immediately but generate only after the latest debounce token.
- Complete `UsageService` with transactional limit checks and usage events.
- Enforce the free and pro generation allowances before calling the LLM.
- Keep `AIContextBuilder` as the only database-to-AI context boundary.
- Add structured-output validation and at most one repair retry.
- Record provider/model/token/cost metadata without prompts or message text.
- Add graceful provider timeout, invalid-schema and quota errors.
- Add stale-generation detection based on the actual latest incoming message.
- Add deterministic fake LLM and clock implementations for tests.

### Exit criteria

- Three rapid messages produce one analyzer and one reply-generation cycle.
- `AI OFF` produces zero LLM calls.
- Exceeded allowance produces zero LLM calls.
- Every successful generation contains exactly three unique, validated options.
- Prompt-injection fixtures cannot introduce recipients, tools or executable
  commands into the send path.

## 8. Milestone 4 — Closed-beta Mini App

**Target:** one engineering iteration.

### Deliverables

- Adopt TanStack Query for connection, conversations, detail, suggestions,
  settings and subscription state.
- Complete editable style settings with validation and server persistence.
- Complete privacy actions with confirmation and destructive-action feedback.
- Add explicit edit-before-send UX behind its feature flag.
- Show pending until Telegram confirms success; never optimistically show sent.
- Handle stale suggestions by clearing options and requesting regeneration.
- Add connection instructions tailored to Telegram's current UI.
- Add loading, empty, offline, unauthorized and recoverable error states.
- Add accessible tap targets, keyboard behavior and iPhone safe-area handling.
- Add browser and mobile viewport smoke tests.

### Exit criteria

- A beta user can finish onboarding and the complete reply flow without API tools.
- No UI accepts an authoritative recipient identifier.
- Send success is shown only after backend confirmation.
- Safari/iPhone, Telegram WebView, Chrome and desktop layouts pass smoke tests.
- Product copy accurately describes Telegram access and privacy boundaries.

## 9. Milestone 5 — Retention, summaries and safe memory

**Target:** one engineering iteration after the closed beta is stable.

### Deliverables

- Run scheduled raw-text cleanup with locking, metrics and failure alerts.
- Implement incremental summaries with a message cursor and version checks.
- Define and enforce the allowlist of non-sensitive memory categories.
- Keep memory extraction disabled by default until privacy evaluation passes.
- Add sensitive-category rejection fixtures for health, sexual life, religion,
  politics, finance, credentials, documents, home address and geolocation.
- Add per-conversation memory inspection/deletion APIs if memory extraction ships.
- Ensure summaries and memories are removed by both memory and account deletion.

### Exit criteria

- Raw text older than the configured retention period is removed by an automated
  job without breaking deduplication metadata.
- Summary jobs are idempotent and cannot cross tenant boundaries.
- Sensitive fixtures never become durable memory.
- Users can erase all AI-specific context and verify an empty result.

## 10. Milestone 6 — Telegram Stars and subscription enforcement

**Target:** one engineering iteration.

### Deliverables

- Verify the current official Stars recurring-subscription constraints.
- Implement `TelegramStarsProvider` invoice creation.
- Handle `pre_checkout_query` and `successful_payment` idempotently.
- Persist integer Stars amounts and unique Telegram charge IDs.
- Activate, renew, cancel and expire subscriptions transactionally.
- Reconcile subscription state and usage allowance before AI calls and sends.
- Add billing-disabled behavior that does not affect the free plan.
- Add payment-event tests for duplicates, wrong user, expiration and replay.

### Exit criteria

- Duplicate payment updates activate a subscription exactly once.
- An expired subscription immediately uses the correct plan allowance.
- No monetary value is stored as a float.
- Billing code cannot unlock a conversation or bypass the send ACL.

## 11. Milestone 7 — Production readiness

**Target:** one to two engineering iterations.

### Deliverables

- Add CI for backend lint/type/tests, frontend lint/type/build and migration checks.
- Add Caddy HTTPS deployment example and production security headers.
- Add Redis/PostgreSQL readiness, graceful shutdown and connection-pool tuning.
- Export privacy-safe metrics for webhook, AI, send, connection and cost events.
- Add alerting runbooks for webhook failures, send unknowns and cleanup failures.
- Add secret rotation, database backup/restore and deletion runbooks.
- Add load tests for webhook bursts and concurrent suggestion/send requests.
- Perform dependency, container and infrastructure security scans.
- Conduct a final threat-model review and a restore/fire-drill exercise.

### Exit criteria

- Staging deployment passes migration, rollback, backup and restore exercises.
- No critical or high security finding remains unresolved.
- SLOs and alerts exist for the core reply flow.
- Closed-beta telemetry contains no conversation content or contact identity.
- Production launch has an explicit go/no-go checklist and named owners.

## 12. Post-MVP candidates

These items may be evaluated only after production readiness:

- improved user-controlled style learning;
- optional user-reviewed safe-memory proposals;
- richer non-text message context supported by the official Bot API;
- additional subscription plans and entitlement reporting;
- internal support tooling limited to identifiers, connection state, usage and
  errors—never private conversation content.

Explicitly out of scope remain autopilot, cold outreach, mass messaging,
scraping, userbots, MTProto user sessions, social scoring and cross-platform CRM.

## 13. Suggested release sequence

| Release | Included milestones | Audience |
|---|---|---|
| `0.1.0` | 0–2 | Engineering and security testing |
| `0.2.0` | 3 | Internal dogfood |
| `0.3.0` | 4 | Invite-only closed beta |
| `0.4.0` | 5 | Privacy-reviewed beta |
| `0.5.0` | 6 | Paid beta through Telegram Stars |
| `1.0.0` | 7 | Production launch |

## 14. Immediate next sprint

The next sprint should execute **Milestone 0** and the test harness portion of
**Milestone 1**. Its concrete backlog is:

1. Refactor backend modules and introduce external-gateway dependency injection.
2. Build PostgreSQL integration fixtures and fake Telegram/LLM adapters.
3. Replace the initial migration with explicit Alembic operations.
4. Implement the required tenant, ACL, idempotency and send test matrix.
5. Add CI and make all checks mandatory before proceeding to feature work.

This sequence prevents new features from being built on unverified privacy and
recipient-safety assumptions.
