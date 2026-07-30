# PalWakf Connected Orchestrator V1

Fail-closed communication plane between authenticated HTTP or Streamable HTTP
MCP clients, an OpenAI Agents SDK planner, and Codex.

## Boundaries

```text
SUPABASE_CONNECTED=FALSE
PRODUCTION_MUTATION=FALSE
SECRET_VALUES_PERSISTED=FALSE
PUBLIC_UNAUTHENTICATED_ENDPOINT=FALSE
LOCAL_OPERATIONAL_STATE=SQLITE
```

The service verifies governed repository state before Codex execution. Source
mutation still requires the task authority envelope and all repository gates.

## Runtime

Python 3.12 is required:

```bash
python -m pip install -e "./orchestrator[dev]"
```

`OPENAI_API_KEY` is inherited from the process environment and is never
returned, persisted, or read from repository files. Connected clients also
require scoped service authentication. Local opaque bearer values are
configured by SHA-256 digest only in `PALWAKF_AUTH_CLIENTS_JSON`.

```bash
python orchestrator/main.py serve --live-agents
```

The default is `LOCAL_SECURE_MODE` on `127.0.0.1:8421`. Readiness fails when
client authentication is absent. Remote mode requires a stable HTTPS resource,
OAuth issuer, audience, and JWKS endpoint. See
`docs/contracts/CONNECTED_SERVICE_AND_CHATGPT_MCP_V1.md`.

## Contracts

- `GET /health` and `GET /ready`: authenticated lifecycle state.
- `POST /v1/connected/tasks/dispatch`: bounded governed dispatch.
- `GET /v1/tools/health`: evidence-backed tool operational health.
- `/mcp/`: authenticated Streamable HTTP MCP with six lifecycle tools.

HTTP and MCP share the same application service, SQLite persistence,
idempotency records, queue limits, one-writer repository locks, host binding,
authorization, and audit events. Repeating an idempotency key across process
restarts returns the persisted task without silently creating another
execution.

Run the deterministic transport acceptance:

```powershell
.\scripts\smoke_connected_service.ps1
```
