# External Project Intake and Reality Adapter V1

## Authority

```text
MODE=READ_ONLY_ZERO_MUTATION
NO_EXTERNAL_SOURCE_MUTATION=TRUE
NO_DEPENDENCY_INSTALL=TRUE
NO_SUPABASE_CONNECTION=TRUE
NO_PRODUCTION_PROMOTION=TRUE
```

## Adapter Boundary

`ProjectRealityAdapter.probe()` returns an
`ExternalProjectRealityReport`. The GitHub adapter owns only an HTTP `GET`
client. The local Git adapter requires an exact resolved allowlist match and
permits only:

```text
git rev-parse --show-toplevel
git rev-parse HEAD
git branch --show-current
git status --porcelain=v1
git remote get-url origin
```

All other local Git commands are rejected.

## Bounded Discovery

- At most 500 file records are scanned.
- Safe metadata reads are capped at 256,000 bytes per file.
- `.env`, credential, key, and certificate names are recorded as risk facts;
  their contents are not read.
- Identity mismatch, missing repository, invalid HEAD, unavailable adapter, and
  disallowed local path return typed fail-closed blockers.

## Deterministic Baseline

The fingerprint is SHA-256 over canonical identity, branch, HEAD, stack,
commands, CI, deployment, tree summary, indicators, source references, tool
profile, and candidates. Observation time and prior HEAD are excluded so a
replay of unchanged facts returns the same fingerprint.

## Tool Profile

`PROJECT_CAPABILITY_PROFILE_V1` persists:

- selected: GitHub reads and Workspace Manager evidence storage;
- conditional: Vercel read-only discovery, exact-allowlist local Git, and Figma
  only for later material UI work;
- excluded: tools without concrete intake evidence;
- blocked: Supabase and all database-connected capabilities.

## Prepare-Only Contract

`POST /v1/projects/{project_id}/prepare-task` locks a selected candidate to the
observed HEAD and returns:

```json
{
  "prepared_only": true,
  "dispatched": false
}
```

It never creates a branch, commit, pull request, deployment, database
connection, or automatic dispatch.
