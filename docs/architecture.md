# Architecture
## System context
```mermaid
flowchart LR
U[User / Mini App]-->API[FastAPI SaaS API]
TG[Telegram Business Bot API]-->API
API-->PG[(PostgreSQL)]
API-->R[(Redis)]
API-->AI[LLM Provider]
```
## Webhook flow
```mermaid
flowchart TD
W[Webhook]-->S{Secret valid?}--no-->X[Reject]
S--yes-->T[Resolve business connection / tenant]-->A{Active?}--no-->D[Drop]
A--yes-->C[Find/create conversation, default AI OFF]-->M{Copilot?}
M--no-->O[Metadata only]
M--yes-->P[Idempotently retain text]
```
## AI generation flow
```mermaid
flowchart LR
ACL[AccessService]-->CTX[Context Builder]-->AN[Structured Analyzer]-->GEN[3 structured replies]-->DB[(Generation)]
```
## Send flow
```mermaid
flowchart TD
H[Explicit authenticated request]-->ACL[Second ACL check]-->F{Fresh and unsent?}--no-->R[409]
F--yes-->RES[Transactional reservation]-->TG[sendMessage with server-owned recipient]-->SYNC[Persist outgoing]
```
## Tenant isolation
Every repository query for user content includes authenticated `user_id`; conversation ID alone is never authoritative. Connection, generation and conversation ownership are jointly checked at the domain boundary.
## Privacy boundary
Telegram recipient restrictions are the first boundary and the application ACL is the second. New conversations are `AI OFF`; text is discarded before persistence while off. LLM context contains semantic text only, never Telegram credentials or authoritative recipient IDs.
