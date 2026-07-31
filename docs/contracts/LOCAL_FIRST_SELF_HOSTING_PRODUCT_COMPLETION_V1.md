# Local-First Self-Hosting Product Completion V1

## Runtime Contract

`Start-PalWakfWorkspaceManager.ps1` is the repository-root entry point. It:

- resolves the repository root from its own location;
- validates the governed branch, Python runtime, Flutter runtime, and API key
  presence without printing sensitive values;
- builds Flutter Web and serves it from the loopback Orchestrator;
- creates a random local bearer in process memory and persists only its
  Windows-protected form under ignored `.palwakf/` runtime state;
- issues a one-time loopback launch nonce and exchanges it for an HttpOnly,
  SameSite local session cookie;
- waits for authenticated readiness and registers Workspace Manager from real
  local Git, remote Git, GitHub PR, CI, and Vercel status reads;
- recovers stale runtime state and does not duplicate a healthy process.

`Stop-PalWakfWorkspaceManager.ps1` validates the recorded process identity,
stops it, and removes only the ignored local runtime record.

## Self-Hosting Authority

Workspace write is denied for every dispatch except:

```text
TASK_ID=PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1
IDEMPOTENCY_KEY=palwakf-self-hosted-last-execution-card-v1
```

That task must be created by the authenticated local product, explicitly
authorized against the exact Bootstrap HEAD, and dispatched once through the
bounded queue. The existing branch and PR are the only allowed Git targets.

The executor must not access secrets, Supabase, databases, deployments,
production, Pal_Eyes, or any external project. Codex command identifiers,
redacted command summaries, redacted output excerpts, and exit codes are
persisted as correlated tool receipts.

## Verification And Resume

The task remains pending verification until GitHub Actions reports success for
its exact result HEAD. The verification receipt is persisted in the same local
SQLite task store. Restart recovery restores the project, task, authorization,
thread, execution receipt, tool receipts, verification, and writer state.

The protected Vercel Preview remains a static UI surface. Automatic dispatch
requires this authenticated loopback runtime and is never promoted to
Production by this contract.

## Prohibited Actions

- no second live self-hosted execution;
- no replacement task ID, thread, branch, PR, or idempotency key;
- no merge or Production promotion;
- no Supabase or external database connection;
- no external-project inspection or mutation;
- no plaintext sensitive value in source, logs, screenshots, evidence, or Git.
