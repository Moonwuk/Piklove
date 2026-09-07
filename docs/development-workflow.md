# Development workflow

Piklove uses a lightweight evidence-first workflow. It borrows the useful parts of structured
agent methodologies without making every change go through a design document, worktree, or
multi-agent review.

## Scale the process to the risk

| Change | Expected preparation | Examples |
| --- | --- | --- |
| Small | Inspect the affected code, make the focused change, run relevant checks | Copy, styling, comments, dependency metadata |
| Bounded | Write a short approach and identify the observable acceptance criteria | Endpoint behavior, UI state, adapter change |
| Architectural | Document alternatives, privacy and failure semantics; get approval before coding | Billing, retention architecture, memory extraction, new external integration |

Security-sensitive and destructive work always receives explicit review regardless of size.

## Debug from evidence

For bugs and failing checks:

1. Reproduce the symptom with the smallest reliable command or request.
2. Trace the failing data and control flow across component boundaries.
3. State the root cause and the behavior the fix must preserve.
4. Add a regression test that fails for that cause when practical.
5. Implement the smallest complete fix and rerun the focused test.
6. Run the broader checks for every affected subsystem.

A workaround that only hides an exception, weakens an assertion, or skips a check is not a fix.

## Test observable behavior

- A test should name the production regression it detects.
- Prefer API behavior and persisted state over assertions about implementation details.
- Mock paid or external edges such as Telegram and OpenAI. Keep authentication, tenant ACL,
  quota reservation, retention, and persistence real whenever the test scope permits.
- PostgreSQL-specific transaction behavior must be tested on PostgreSQL, not inferred from SQLite.
- Documentation and trivial configuration changes need a meaningful parser/build/check, not a
  synthetic test that merely searches for the edited text.

## Review technically

Treat review feedback as a hypothesis to evaluate:

1. Understand the requested behavior.
2. Verify the comment against the current revision and project constraints.
3. Implement valid findings one coherent group at a time.
4. Explain technically when a suggestion is inapplicable or creates a worse trade-off.
5. Rerun the checks affected by the resolution.

## Finish with fresh verification

The repository CI definition is the source of truth for required automated checks. Locally, run
the relevant backend and web commands listed in `AGENTS.md`, inspect the complete diff, and report:

- commands that passed;
- checks skipped because they were not applicable;
- checks blocked by an environment limitation;
- any remaining risk that CI or a reviewer must verify.

Previous green output and an unexecuted CI configuration are not evidence that the current change
passes.
