# Product and functional review — closed-beta readiness

Reviewed on 2026-09-14 against the complete owner journey:

`Business Bot connection → Mini App auth → discovered conversation → Copilot opt-in → suggestions → confirmed send → privacy controls`.

## Release blockers fixed in this change

| Severity | Finding | Resolution |
| --- | --- | --- |
| P0 | The production web image ignored the Compose `NEXT_PUBLIC_API_URL` build argument, so a phone could call its own `localhost:8000`. | The Docker build now declares and compiles the public API URL; Compose and `.env.example` expose it explicitly. |
| P0 | The Mini App expected `window.Telegram.WebApp` but never loaded Telegram's Web App script. | The root layout loads the official script before hydration. |
| P0 | Enabling or disabling Copilot replaced full conversation state with a compact API response and then attempted `messages.map`, crashing the screen. | Compact mode updates are merged into the loaded detail state. |
| P1 | A network retry generated a new idempotency key, while the API could replay a key for an unrelated generation. | The UI retains a key for the same request; the API binds replay to user, conversation and generation and gives idempotency precedence over mutable state. |
| P1 | Whitespace-only edited replies passed request validation and became an empty Telegram send. | Input is stripped and rejected before any send reservation. |
| P1 | The product advertised editable replies but the Mini App exposed only direct option sending. | The full edit-and-confirm path is now available. |
| P1 | New Telegram messages did not appear until the user reopened the screen. | Conversation list/detail polling plus manual refresh were added for the beta. |
| P1 | Every slider movement sent a full Settings update; overlapping responses could restore an older value. | Settings are edited locally and committed once with an explicit Save action. |
| P1 | “Clear all AI memory” issued one request per conversation and could finish partially. | A single server-side transaction clears summaries, memory and generations. |
| P1 | Account deletion left the browser session cookie in place. | The delete response now clears the session cookie. |
| P1 | A first Business connection webhook racing first login could acknowledge success after rolling back the connection. | Integrity conflicts are rolled back and retried once; persistent conflicts fail for Telegram retry. |
| P1 | AI response models accepted unexpected fields and whitespace-only options. | Structured output is strict and fail-closed. |

## Testability improvements

- One command builds, starts and performs a product smoke test: `./scripts/beta-test.sh`.
- `--live-ai` adds one real provider call containing only committed synthetic text.
- `--set-webhook` registers the webhook only after the automated gate passes.
- CI now validates shell syntax, Compose configuration and production container builds in addition to
  backend tests, PostgreSQL migrations/concurrency, TypeScript and the Next.js production build.
- The manual path is reduced to eleven observable Telegram steps in `docs/BETA_TESTING.md`.

## Deliberately deferred after the first closed-beta pass

These are important, but adding them immediately would make tomorrow's test less controlled:

1. Redis-backed endpoint rate limiting and generation debounce.
2. Cursor pagination for conversations and long message histories.
3. Browser-level Playwright coverage for the Mini App.
4. Production metrics, alerting, backup/restore and incident drills.
5. Telegram Stars billing and subscription lifecycle.
6. A clean provider-neutral LLM adapter change after real OpenAI-path beta evidence.
7. Dependency audit remediation after identifying the exact runtime advisory and safe target version.

The closed beta remains free, manually confirmed, and small until the first four items are complete.
