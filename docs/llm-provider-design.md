# Pluggable LLM provider design

Status: **approved and implemented — 2026-09-14**

## Goal

Let an operator select DeepSeek API or Ollama Cloud without changing application code, while
preserving Piklove's existing `LLMProvider` domain contract, privacy boundary, quota reservation,
and explicit-send workflow. Make the integration testable without a paid account and provide a
single opt-in smoke test for real credentials.

## Constraints and provider capabilities

- DeepSeek documents an OpenAI-compatible chat API at `https://api.deepseek.com` and JSON mode via
  `response_format={"type":"json_object"}`. JSON mode still requires an explicit JSON prompt and
  may occasionally return empty content.
- Ollama Cloud exposes its native chat API at `https://ollama.com/api/chat` using bearer API keys.
  Its current documentation explicitly says Cloud does not support structured outputs. Local
  Ollama supports JSON schemas, but that capability must not be assumed for Cloud.
- Piklove needs validated `ConversationAnalysis` and `ReplySuggestions`, not an unchecked string.
  Invalid or empty provider output must fail closed and must never be persisted as a generation.

Official references:

- [DeepSeek quick start](https://api-docs.deepseek.com/)
- [DeepSeek JSON output](https://api-docs.deepseek.com/guides/json_mode)
- [Ollama Cloud API](https://docs.ollama.com/cloud)
- [Ollama authentication](https://docs.ollama.com/api/authentication)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)

## Decision

Introduce two explicit adapters behind the existing `LLMProvider` protocol rather than renaming
DeepSeek or Ollama credentials to `OPENAI_*` or exposing an arbitrary base URL.

1. `DeepSeekProvider` uses `httpx.AsyncClient` and `/chat/completions` in JSON mode.
2. `OllamaCloudProvider` uses `httpx.AsyncClient` and `/api/chat`, asks for JSON in the prompt, and
   validates the returned message locally. It does not claim schema enforcement by Ollama Cloud.
3. `create_llm_provider(settings)` is the only production factory and selects the adapter from an
   enum. Routes do not know provider-specific configuration.
4. Provider output is parsed directly into the existing Pydantic schemas. There is no permissive
   coercion, regex extraction, or persistence before validation.
5. There is no automatic cross-provider fallback. A fallback could disclose the same conversation
   to another processor, duplicate cost, and make quota semantics ambiguous.

DeepSeek should be the first production rollout target because its documented JSON mode is a
better match for Piklove's structured contract. Ollama Cloud remains selectable, but its rollout
is conditional on the live contract test passing for the chosen model.

## Configuration

Replace provider-specific `OPENAI_*` settings after a deprecation window with:

```dotenv
LLM_PROVIDER=deepseek                  # deepseek | ollama_cloud
LLM_API_KEY=
LLM_ANALYSIS_MODEL=
LLM_REPLY_MODEL=
LLM_SUMMARY_MODEL=
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=1
```

The provider enum determines the hard-coded HTTPS origin. Production configuration must reject an
unknown provider, missing key/models, a non-positive timeout, and an excessive retry count. No
operator-controlled base URL is accepted in production; this prevents accidental transmission of
message content to an unintended host. Tests may inject a transport or adapter directly.

For one release, legacy `OPENAI_*` names are accepted only when `LLM_*` is absent. New names win
deterministically. A later cleanup removes the aliases.

## Request and response contract

Both adapters receive the same system prompt and serialized `AIConversationContext` already built
inside the tenant boundary. They return the same domain objects:

```python
class LLMProvider(Protocol):
    async def analyze_conversation(context) -> ConversationAnalysis: ...
    async def generate_replies(context, analysis) -> ReplySuggestions: ...
```

Each request includes a compact JSON example derived from the Pydantic schema. DeepSeek additionally
uses JSON mode. Ollama Cloud receives the same schema in prompt text, because Cloud currently does
not enforce the `format` schema feature. The response path is always:

1. Require a non-empty assistant message.
2. Decode exactly one JSON document.
3. Validate it with the expected Pydantic model.
4. Reject extra or malformed values according to the domain schema.
5. Return the validated object to `SuggestionService`.

Do not ask the model to return Telegram IDs, API credentials, or authoritative recipient data.

## Failure and quota semantics

Use a provider-neutral exception taxonomy:

- `LLMNotConfigured` -> `503 AI_PROVIDER_NOT_CONFIGURED`;
- `LLMTimeout` -> `504 AI_PROVIDER_TIMEOUT`;
- authentication or unavailable upstream -> `503 AI_PROVIDER_UNAVAILABLE`;
- empty, malformed, or schema-invalid output -> `502 AI_PROVIDER_INVALID_RESPONSE`.

Responses contain the existing content-free request ID. Logs may contain provider name, model,
latency, HTTP status class, attempt count, and error code, but never prompts, message text, raw
responses, usernames, chat titles, or arbitrary provider bodies.

The existing quota reservation remains immediately before the first provider call. Once that call
starts, the reservation remains consumed on timeout or failure because upstream cost is uncertain.
The configured retry budget applies inside a single provider call; the application does not add a
second retry layer. Analysis success followed by reply failure still consumes exactly one Piklove
generation reservation.

## Privacy and security

- AI OFF behavior is unchanged: no message text is retained or sent to a provider.
- Provider selection is deployment-wide, never user-controlled.
- There is no silent fallback or fan-out between providers.
- API keys remain backend-only and must be redactable by field name in configuration diagnostics.
- All provider hosts are fixed HTTPS origins in production.
- The privacy policy describes provider-side processing instead of assuming that an unsupported
  request hint changes provider retention.
- Sending remains a separate explicit user action and never becomes an LLM capability.

## Implementation slices

### Slice 1 — provider-neutral core

- Move shared prompts, JSON parsing, exceptions, and factory selection into a provider package.
- Make Pydantic output schemas reject unexpected fields.
- Convert the route from constructor-specific error handling to the neutral error taxonomy.
- Keep the current fake provider used by HTTP flow tests.

### Slice 2 — DeepSeek

- Implement chat-completions requests and JSON mode.
- Add recorded, secret-free request/response fixtures for valid, empty, malformed, timeout, 401,
  429, and 5xx cases.
- Record the actual provider/model on `Generation`.

### Slice 3 — Ollama Cloud

- Implement native `/api/chat` requests with bearer authentication and `stream=false`.
- Validate prompt-requested JSON locally and fail closed on deviations.
- Gate deployment on the chosen model passing the optional live contract test.

### Slice 4 — migration and operations

- Add the `LLM_*` environment variables and legacy alias tests.
- Update README, deployment examples, health diagnostics, and secret-rotation documentation.
- Remove the unused OpenAI SDK only after both adapters use HTTPX.

No database migration is expected: the existing generation `provider` and `model` columns can store
the selected provider and concrete model.

## Test strategy

All required tests run without network access or paid credentials:

```bash
cd apps/api
ruff check .
ruff format --check .
python -m pytest tests/ -q
```

Adapter contract tests use `httpx.MockTransport`, inspect the outbound host, authorization header,
model, prompts, timeout/retry behavior, and feed deterministic JSON fixtures back. They must prove:

- both adapters produce identical domain objects from valid responses;
- invalid/empty output is never persisted;
- timeout, 401, 429, and 5xx map to stable content-free API errors;
- neither request nor logs include Telegram credentials or recipient IDs;
- AI OFF never invokes an adapter;
- one failed provider operation consumes no more than one Piklove quota reservation.

An opt-in script makes a minimal real call and performs no database writes:

```bash
LLM_LIVE_TEST=1 LLM_PROVIDER=deepseek LLM_API_KEY=... \
  python -m pytest tests/live/test_llm_contract.py -q
```

The same command with `LLM_PROVIDER=ollama_cloud` validates the selected Ollama Cloud model. Live
tests are skipped by default and must send only synthetic text committed in the test, never user
or production data.

## Acceptance criteria

- Switching providers requires environment changes only.
- The ordinary test suite is deterministic and needs no external LLM account.
- A documented single command validates real credentials and model compatibility.
- Malformed model output cannot reach `Generation` or the send flow.
- Provider failures expose stable error codes and content-free logs.
- AI OFF, tenant isolation, atomic quota reservation, and explicit-send invariants remain covered.

## Explicitly deferred

- automatic provider failover or per-user provider choice;
- streaming suggestions;
- model discovery at application startup;
- semantic retries that send the conversation to the model again;
- local self-hosted Ollama deployment support (it can be designed separately if required).
