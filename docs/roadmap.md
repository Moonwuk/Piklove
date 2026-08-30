# Piklove roadmap

This roadmap keeps the product privacy-first: Piklove remains a user-confirmed copilot, not an
autopilot, and it only processes conversations delivered through the official Telegram Business
Bot API.

## Now — stabilize the MVP

- Enforce secure production configuration and consistent, content-free API errors.
- Make webhook ingestion resilient to duplicate, edited, deleted and out-of-order updates.
- Add database migration, access-control, retention and confirmed-send integration tests.
- Add bounded timeouts, rate limits, debounce locks and operational metrics without message text.
- Wire style, privacy controls and account deletion through the Mini App.

## Next — production beta

- Run retention cleanup and summary jobs through a monitored scheduler.
- Complete Telegram Stars invoices, pre-checkout validation, quotas and cancellation.
- Add safe summary and allowlisted memory extraction with visible erase controls.
- Document backup/restore, secret rotation, incident response and data-deletion procedures.
- Validate Telegram permission changes and uncertain send outcomes without blind retries.

## Later — product quality

- Improve reply quality using opt-in, privacy-preserving feedback and evaluation datasets.
- Add localization and accessibility coverage for the Mini App.
- Add team-ready observability dashboards and service-level objectives.
- Evaluate additional official messaging integrations behind the same tenant and consent boundaries.

## Explicit non-goals

- Userbot or MTProto account login, scraping, contact discovery or mass messaging.
- Automatic sending, recipient selection or bypassing Telegram Business permissions.
- Persisting message text while Copilot is disabled or placing conversation content in logs.
