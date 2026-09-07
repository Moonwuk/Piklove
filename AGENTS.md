# Piklove agent workflow

These instructions apply to the whole repository. Keep the process proportional
to the change: use the safeguards below, but do not create ceremony that does not
improve the result.

## Before editing

1. Read the relevant architecture, threat-model, and roadmap sections.
2. Classify the work:
   - **Small:** localized, low-risk, and behavior-preserving. Inspect, edit, and verify directly.
   - **Bounded:** changes existing behavior in one subsystem. State a short approach before editing.
   - **Architectural:** crosses trust boundaries, data ownership, billing, retention, or multiple
     subsystems. Write a design in `docs/` and obtain user approval before implementation.
3. For a bug or failed check, reproduce it and identify the root cause before changing code.
   Do not treat a suppressed exception, relaxed assertion, or disabled check as a fix.

## Implementation

- Preserve the privacy boundaries in `docs/threat-model.md`: AI OFF stores no message text,
  all reads and writes remain tenant-scoped, and sending always requires explicit user action.
- Add a regression test before the fix when it can exercise observable behavior. For prose,
  generated files, and trivial configuration changes, use the narrowest meaningful validation
  instead of a ceremonial test.
- Prefer real components at system boundaries. Mock Telegram and OpenAI calls, not Piklove's
  access-control, quota, persistence, or send-reservation logic.
- Treat migrations as immutable snapshots. Model changes require a new Alembic revision; never
  alter an applied revision to evolve an existing database.
- Evaluate review comments against the code and requirements before implementing them. Resolve
  ambiguity with evidence or ask a focused question; do not accept suggestions mechanically.
- Do not require subagents or a new worktree for routine changes. Use them only when explicitly
  requested or when the execution environment's instructions call for them.

## Verification

Run the checks relevant to every changed area and report the exact commands and outcomes.
Do not claim a check passed unless it completed successfully in the current turn.

Backend:

```bash
cd apps/api
ruff check .
ruff format --check .
python -m pytest tests/ -q
```

When PostgreSQL behavior or migrations change, also run the PostgreSQL concurrency tests and an
Alembic `upgrade head` / `check` / `downgrade base` round-trip using a disposable database.

Web:

```bash
cd apps/web
npm run typecheck
npm run build
```

Before finishing, inspect `git diff --check`, the complete diff, and `git status`. Distinguish a
real failure from a skipped check or an environment limitation in the final report.
