# GOVERNED_TRANSACTIONAL_FILE_APPLY_V1

Status: IMPLEMENTED_FOUNDATION_CANDIDATE
Scope: Workspace Manager local source mutation capability
Remote mutation: forbidden
Commit/push: outside this capability

## Purpose

Provide one reusable source-file mutation engine instead of task-specific PowerShell APPLY scripts.
The engine is fail-closed, transactional, idempotent, resumable, repository-bound, and evidence-producing.

## Canonical text policy

Every postimage is written as:

- UTF-8 without BOM.
- LF line endings.
- Exactly one final LF at EOF.
- SHA-256 verified from the bytes read back after write.

## Repository gates

Before mutation the request binds to:

- repository identity;
- exact branch;
- exact 40-character HEAD;
- a bounded target-file set;
- no dirty worktree paths outside that set.

Git inspection is read-only. This capability never fetches, commits, pushes, merges, or contacts a remote provider.

## File classifications

Each target is classified before mutation:

- `CLEAN_PREIMAGE`: absent when absence is required, or canonical bytes match the declared preimage hash.
- `ALREADY_POSTIMAGE`: raw bytes already equal the canonical postimage hash.
- `PARTIAL_POSTIMAGE`: semantic/canonical bytes equal the postimage but raw representation differs (for example BOM, CRLF, or missing EOF LF).
- `FOREIGN_DRIFT`: any undeclared state; mutation is blocked.

`ALREADY_POSTIMAGE` is a verified no-op. `PARTIAL_POSTIMAGE` is safely normalized to the canonical postimage.

## Transaction model

1. Plan and classify all targets.
2. Acquire the repository writer lock.
3. Re-plan under lock.
4. Stage every canonical postimage and verify its hash.
5. Capture raw preimages for every file that will change.
6. Apply with atomic per-file replacement.
7. Read back and verify every postimage.
8. On any failure, restore every already-mutated raw preimage in reverse order and delete newly created files.
9. Persist the mutation journal in the Workspace `StateStore`.

## Persistent journal

The journal stores no file content or secrets. It records:

- task/run identity;
- repository/branch/expected HEAD;
- deterministic manifest SHA-256;
- per-file classification;
- changed paths;
- lifecycle state;
- failure/rollback state.

Lifecycle states:

`PLANNED → PREPARED → STARTED → APPLIED → VERIFIED`

or fail-closed terminal states:

`BLOCKED / ROLLED_BACK / FAILED`.

## Security boundaries

- Relative repository paths only.
- Path traversal and absolute paths forbidden.
- Symlink targets forbidden.
- UTF-8 text files only in V1.
- Unrelated worktree drift blocks mutation.
- One active repository writer at a time.
- No arbitrary shell execution.
- No database mutation.
- No production mutation.
- No Git remote mutation.

## CLI

`orchestrator/scripts/governed_file_apply.py` consumes a JSON `GovernedFileApplyRequest` manifest.
Use `--plan-only` before mutation when preparing a new governed change.
The default journal database is `.palwakf/orchestrator.sqlite3` inside the repository.

## Acceptance boundary for V1 foundation

V1 foundation is accepted only when tests prove:

- canonical UTF-8/LF/EOF behavior;
- idempotent reapply;
- recovery of BOM/CRLF/EOF-only partial postimages;
- foreign drift rejection;
- unrelated dirty-file rejection;
- rollback after an injected mid-transaction failure;
- path escape rejection;
- repository writer lock enforcement.
