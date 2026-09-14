# Review of howdeploy projects

Reviewed: 2026-09-14. The supplied URL is a GitHub user profile, not one repository. Its public
API listed 31 repositories at review time. This review therefore prioritized the projects relevant
to Piklove's agent workflow, provider boundary, validation, security, and Telegram integration.

Pinned review revisions: `LocalForgeLLM@f698635`, `pizdec@59eafbb`, `remorafish@e7f9c05`,
`kisa-stack@63c6f6b`, `Z.A.E.B.A.L@ea5e18f`, `wiki@aee6158`, and `telegram-mcp@63b9168`.

## Reviewed projects

- [LocalForgeLLM](https://github.com/howdeploy/LocalForgeLLM): repeatable runtime profiles,
  capability-based validation, source provenance, and honest separation of measured results from
  estimates.
- [PIZDEC](https://github.com/howdeploy/pizdec): read-only, evidence-driven security review with
  explicit scope, stable findings, confidence, exclusions, and observable acceptance criteria.
- [RemoraFish](https://github.com/howdeploy/remorafish): provider contracts, conformance tests,
  adapter isolation, neutral errors, and separation of control-plane credentials from model calls.
- [kisa-stack](https://github.com/howdeploy/kisa-stack): compact agent instructions emphasizing
  local conventions, surgical changes, behavior tests, and direct reporting of uncertainty.
- [Z.A.E.B.A.L.](https://github.com/howdeploy/Z.A.E.B.A.L): escalating self-audit when repeated user
  frustration indicates that an agent is repeating an incorrect assumption.
- [wiki](https://github.com/howdeploy/wiki): indexed, testable documentation and repository-hygiene
  checks.
- [telegram-mcp](https://github.com/howdeploy/telegram-mcp): Telegram automation through MTProto,
  broad message tools, path allowlists, and input validation.

The remaining public repositories were inventoried by GitHub metadata and screened by purpose.
Projects centered on UI customization, entertainment personas, network-circumvention setup, audio,
or unrelated desktop tooling were not reviewed file-by-file because they do not inform Piklove's
current product or trust boundaries.

## What was adapted

### One verification entrypoint

LocalForgeLLM consistently distinguishes startup, protocol, quality, performance, and recovery
evidence instead of treating one successful command as proof of everything. Piklove now exposes
the same idea through `scripts/verify.sh`:

```bash
./scripts/verify.sh fast       # backend checks/tests + web typecheck
./scripts/verify.sh full       # fast checks + production web build + diff hygiene
./scripts/verify.sh postgres   # destructive round-trip on an explicitly disposable database
./scripts/verify.sh live-llm   # synthetic contract request to the selected LLM provider
```

The modes stay separate because offline tests, PostgreSQL concurrency, production frontend builds,
and paid external inference establish different facts. A skipped live or PostgreSQL check is not a
pass.

### Provider conformance at the boundary

RemoraFish's useful idea is its adapter contract and conformance suite, not its use of private web
sessions. Piklove applies the contract approach to official DeepSeek and Ollama Cloud APIs:

- deterministic HTTP transport tests run without credentials;
- both adapters return the same Pydantic domain objects;
- provider-specific envelopes do not leak into routes or persistence;
- a separate opt-in live test detects upstream/model drift using synthetic data.

### Evidence-oriented reporting

PIZDEC's strongest reusable pattern is distinguishing confirmed evidence, exclusions, and the
observable condition that proves a fix. Piklove already requires exact commands in PRs; the new
verification modes make those commands stable and make environment-limited checks explicit.

### Research ledger rather than copied tooling

The useful upstream ideas are recorded here with links and review date. No external skill, hook,
prompt, runtime, or source file is vendored. This avoids hidden behavior changes and license/update
burden while retaining traceable provenance.

## What was deliberately rejected

### MTProto and autonomous Telegram tools

`telegram-mcp` signs in as a Telegram account and offers chat discovery, history access, message
sending, contact operations, and other autonomous tools over MTProto. Piklove explicitly supports
only official Business Bot updates, never userbot login, scraping, mass messaging, arbitrary chat
selection, or model-controlled sending. Its code and runtime are therefore not integrated.

The reusable security lesson is narrower: validate external identifiers at the boundary and keep
file/network capabilities deny-by-default. Piklove's LLM receives no tools or authoritative
recipient identifiers at all, which is safer for this product.

### Private web-session gateways

RemoraFish intentionally wraps authorized browser sessions and private web protocols. Piklove must
use official paid APIs with operator-managed API keys. Adopting its session import, browser token,
account pool, or anti-bot logic would create unnecessary credential and terms-of-service risk.

### Profanity hooks and large agent bundles

Z.A.E.B.A.L.'s underlying signal is valid: repeated dissatisfaction should trigger assumption
review rather than another cosmetic patch. Installing a message hook or persistent incident state
is disproportionate here. The existing repository workflow already requires root-cause evidence,
review validation, and fresh checks. Likewise, importing the whole kisa-stack would duplicate and
potentially conflict with `AGENTS.md`.

### Local model optimization

LocalForgeLLM is valuable if Piklove later self-hosts Ollama on owned hardware. The current decision
is Ollama **Cloud**, so GPU selection, quantization, llama.cpp builds, and tuning profiles would add
operational work without helping the selected deployment. Revisit it only after a deliberate local
inference architecture decision.

## Follow-up candidates

1. Add a scheduled read-only security review with a stable report template inspired by PIZDEC,
   without installing third-party agent hooks.
2. Add provider contract fixtures for every production model version and run the opt-in live check
   before changing `LLM_*_MODEL` values.
3. Add a small benchmark record for response validity, end-to-end latency, and cost using synthetic
   conversations; do not compare providers without identical workloads.
4. If local Ollama becomes a requirement, evaluate LocalForgeLLM in a separate design covering
   hardware, data locality, model quality, capacity, and recovery.

These are recommendations, not claims that upstream code has been audited for production use.
