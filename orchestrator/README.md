# PalWakf Orchestrator Backend V1

Local, fail-closed communication plane between an OpenAI Agents SDK planner and
Codex through either the Python SDK or the Codex MCP server.

## V1 boundaries

```text
NO_DATABASE_WRITE=TRUE
NO_PRODUCTION_MUTATION=TRUE
NO_SECRET_ACCESS=TRUE
CODEX_SANDBOX=READ_ONLY
CODEX_APPROVALS=DENY_ALL
REMOTE_DEPLOYMENT=DISABLED
```

The service verifies the governed repository, branch, clean worktree, local
HEAD, and remote HEAD before dispatch. Any mismatch blocks execution.

## Runtime

Python 3.12 is required. Install the project into an isolated environment:

```bash
python -m pip install -e "./orchestrator[dev]"
```

`OPENAI_API_KEY` must be supplied by the runtime secret manager. It is never
read from source files, returned by the API, or written by this project.

Health check:

```bash
python orchestrator/main.py health
```

Local server:

```bash
python orchestrator/main.py serve
```

The server binds to `127.0.0.1:8421` by default. Remote binding is rejected in
V1.

## API

- `GET /health`: static readiness and sovereignty boundaries.
- `POST /v1/dispatch`: governed read-only dispatch.

See `data/read_only_dispatch.example.json` for the request contract. Replace
the fail-closed `0000000` placeholder with the currently governed Git SHA
before dispatch. The `expected_head` field accepts a 7-40 character SHA prefix.
Both SDK and MCP transports use an ephemeral Codex thread and prohibit approval
prompts.
