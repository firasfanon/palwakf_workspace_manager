# Connected Service and ChatGPT MCP V1

## Boundaries

The connected Orchestrator is an authenticated control-plane service. It does
not connect Supabase, mutate production, or expose a public unauthenticated
route. Operational state is stored only in the local SQLite file under
`.palwakf/`, which is excluded from Git.

```text
LOCAL_SECURE_MODE=DEFAULT
REMOTE_OR_TUNNEL_MODE=FAIL_CLOSED_UNLESS_COMPLETE_OAUTH_CONFIGURATION
PUBLIC_UNAUTHENTICATED_ENDPOINT=FALSE
SUPABASE_CONNECTED=FALSE
PRODUCTION_PROMOTION=FALSE
```

## Authentication

Local clients use opaque bearer values whose SHA-256 digests and scopes are
provided to the process in `PALWAKF_AUTH_CLIENTS_JSON`. Plaintext bearer values
are never configured in source, persisted in SQLite, logged, or embedded in the
Flutter Web build. The Flutter operator enters the service token at runtime and
the value remains only in application memory.

Remote OAuth access tokens are verified against an issuer, audience, expiry,
and JWKS signing key. Remote mode requires all of:

```text
PALWAKF_SERVICE_MODE=REMOTE_OR_TUNNEL_MODE
PALWAKF_PUBLIC_BASE_URL=https://...
PALWAKF_OAUTH_AUTHORIZATION_SERVER=https://...
PALWAKF_OAUTH_JWKS_URL=https://.../.well-known/jwks.json
PALWAKF_OAUTH_AUDIENCE=https://.../mcp
```

Missing values, non-HTTPS resource URLs, invalid signatures, expired tokens,
issuer mismatch, or audience mismatch fail closed. Client identity is derived
from `client_id` or `sub`; authority is derived separately from the granted
scope claim.

Scopes:

```text
tasks:read
tasks:dispatch
tasks:continue
tasks:cancel
tasks:verify
tools:probe
```

## HTTP and MCP parity

HTTP and Streamable HTTP MCP call the same `ConnectedApplicationService`.
Both transports share persistence, idempotency, queue limits, repository writer
locks, host binding, authorization, and audit events.

MCP tools:

```text
dispatch_codex_task
continue_codex_task
get_codex_task_status
cancel_codex_task
verify_codex_result
list_recent_tasks
```

The MCP resource is mounted at `/mcp/`. In remote mode the MCP server publishes
OAuth protected-resource metadata from the configured authorization server and
resource URL.

## Persistence and concurrency

- SQLite uses WAL and immediate transactions for state replacement and writer
  acquisition.
- Queue capacity and worker count are bounded by settings.
- One active workspace writer is permitted per repository.
- Interrupted queued or running tasks recover as failed without automatic
  duplicate execution and can be explicitly continued.
- Every Codex thread persists `execution_host_id` and `tool_executor_id`.
- Continue and verify reject incompatible host or executor identities. Host
  migration requires a future explicit handshake and is not silently inferred.

## Tool operational health

Authenticated APIs:

```text
GET  /v1/tools/health
GET  /v1/tools/{adapter_id}/health
GET  /v1/tools/alerts
POST /v1/tools/{adapter_id}/probe
```

Every fact includes provenance and observation time when available. Unknown
balance, cost, quota, renewal, and expiry remain null with
`NOT_EXPOSED_BY_PROVIDER`; values are never invented. OpenAI authentication
`SET` and quota `AVAILABLE` are seeded only from the independently verified
runtime recovery V3 evidence.

## Acceptance

Run the deterministic fake-executor transport smoke:

```powershell
.\scripts\smoke_connected_service.ps1
```

It starts an authenticated loopback service with an ephemeral in-memory bearer,
uses the official MCP client, and proves dispatch, status, continue, cancel,
verify, recent-task listing, host identity persistence, and unauthenticated
rejection. It prints no token.

ChatGPT connection remains a separate deployment gate. Source readiness and
local MCP interoperability do not claim a live ChatGPT connection until an
authorized stable HTTPS deployment and OAuth server are configured and tested.
