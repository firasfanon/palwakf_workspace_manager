# Current Task

```text
TASK_ID=PALWAKF_WORKSPACE_MANAGER_LOCAL_FIRST_SELF_HOSTING_PRODUCT_COMPLETION_V1
STATUS=BOOTSTRAP_VALIDATED_SELF_HOSTED_PROOF_PENDING
MODE=CONTROLLED_LOCAL_SELF_HOSTING
REPOSITORY=firasfanon/palwakf_workspace_manager
BRANCH=agent/workspace-manager-foundation-v1
PR_NUMBER=1
EXPECTED_BEFORE_HEAD=53e1d2beb54229563445232dec9c5ff32277fccc
BOOTSTRAP_COMMIT=PENDING
SELF_HOSTED_COMMIT=PENDING
SELF_HOSTED_PROOF_TASK=PALWAKF_WORKSPACE_MANAGER_SELF_HOSTED_LAST_EXECUTION_CARD_V1
SELF_HOSTED_PROOF_IDEMPOTENCY_KEY=palwakf-self-hosted-last-execution-card-v1
SELF_HOSTED_PROOF_STATUS=PENDING_AFTER_BOOTSTRAP_COMMIT
LIVE_SELF_HOSTED_EXECUTION_COUNT=0
ONE_COMMAND_START=IMPLEMENTED_VALIDATED
ONE_COMMAND_STOP=IMPLEMENTED_VALIDATED
LOCAL_SESSION=VERIFIED_HTTPONLY_ONE_TIME_LAUNCH
SELF_REGISTRATION=PASS
DASHBOARD_AGGREGATION=AUTHORITATIVE_STORES_AND_LOCAL_REPOSITORY_REALITY
LOCAL_BROWSER_UAT=PASS_AUTOMATED_DESKTOP_AND_NARROW
PRODUCT_ACCEPTANCE=PENDING_LIVE_PROOF_AND_RESTART_RESUME
EXTERNAL_PROJECT_WORK=FROZEN
EXTERNAL_PROJECT_MUTATION=NONE
DATABASE_CONNECTION=NONE
SUPABASE_CONNECTED=FALSE
PRODUCTION_MUTATION=NONE
MERGE_PERFORMED=FALSE
SECRET_VALUES_EXPOSED=FALSE
```

## Acceptance

- One repository-root command starts the authenticated loopback Orchestrator
  and Flutter product without manual credential entry.
- Workspace Manager registers itself from real local Git, remote Git, GitHub
  PR, GitHub Actions, and Vercel commit status.
- The operator UI creates and explicitly authorizes the canonical proof task.
- Only that task can request workspace write, and it is bound to one persistent
  idempotency key and one repository writer.
- Codex shell calls persist redacted, correlated outputs and exact exit codes.
- GitHub Actions must verify the exact self-hosted result HEAD.
- External project work remains frozen and is neither read nor mutated.
- Product acceptance remains pending until the one live proof and controlled
  restart/resume gates pass.
