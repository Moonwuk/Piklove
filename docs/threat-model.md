# Threat model
| Threat | Impact | Mitigation | Remaining risk |
|---|---|---|---|
| Cross-tenant leak | Private data exposure | `user_id` predicates and AccessService ownership checks | Programming errors require review and tests |
| Stolen bot token | Telegram impersonation | Secret manager, rotation, no frontend exposure | Telegram access until revoked |
| Stolen OpenAI key | Cost/data abuse | Backend-only key and rotation | Provider account abuse window |
| Database compromise | Stored content exposure | Minimal retention, AI OFF text discard, least privilege, encryption at rest | Recent Copilot text exists |
| Webhook spoofing | Forged state/messages | Telegram secret-token header and HTTPS | Secret leakage |
| Prompt injection | Policy bypass | Messages treated as untrusted data; no tools/credentials | Model may produce poor text reviewed by human |
| Incorrect recipient | Message sent to wrong chat | Recipient exclusively loaded from owned conversation | Corrupted DB state |
| Stale suggestion | Contextually wrong reply | Source cursor and incoming-message stale check | Edits outside received updates |
| Duplicate send | Duplicate private message | Idempotency key, unique reservation, no blind retry | Timeout can remain `unknown` |
| Connection revoked | Unauthorized send | Current enabled/can_reply second check | Race after check handled by Telegram rejection |
| Malicious frontend | ACL bypass | Server auth, validation, authoritative backend state | Stolen session |
| Admin/internal access | Insider privacy breach | No content admin UI, least privilege, audit controls | Privileged DB operators |
| Sensitive logs | Long-lived leakage | Allowlisted structured logging fields | Third-party infrastructure metadata |
