# Self-Hosting Operational Loop V1

## Authority

Every task persists the exact `task_id`, repository, branch, full
`expected_head`, authority reference, prompt, constraints, sandbox, timeout,
maximum turns, and idempotency key before execution.

## State machine

```text
pending
  -> running
  -> pending_verification
  -> verified

pending/running -> failed | drifted | timed_out | cancelled
failed -> pending only through an explicit Continue action
```

Executor completion never implies independent verification. `verified` requires
a separate verification receipt, matching after HEAD, and successful CI.

## Manual relay

Automatic dispatch remains primary. User relay is available only after a
recorded automatic failure or explicit operator selection.

The canonical manual package contains no credentials, environment values, or
private local paths. Repeating package generation for the same unchanged
idempotency key returns the original package receipt and canonical SHA-256.
Manual acknowledgement and result import do not satisfy automatic-connectivity
acceptance.

## Capability routing

Tasks request capability IDs. The project profile and versioned registry select
the minimum authorized adapter set. Every selected, excluded, blocked, or
substituted adapter has a persisted reason and evidence contract before
execution. A blocked required capability prevents dispatch.

Actual invocation receipts are stored separately and reconciled against the
planned adapters. Missing or unexpected adapters keep reconciliation open.

## Boundaries

```text
DATABASE_CONNECTED=FALSE
SUPABASE_CONNECTED=FALSE
PRODUCTION_MUTATION=FALSE
MERGE_ACTION_AVAILABLE=FALSE
OPENAI_KEY_IN_CLIENT=FALSE
USER_RELAY_IS_AUTOMATIC_ACCEPTANCE=FALSE
```
