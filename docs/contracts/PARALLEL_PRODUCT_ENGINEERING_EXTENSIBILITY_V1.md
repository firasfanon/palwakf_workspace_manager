# PARALLEL_PRODUCT_ENGINEERING_EXTENSIBILITY_V1

Status: IMPLEMENTATION_CANDIDATE
Batch: PALWAKF_WORKSPACE_PRODUCT_ENGINEERING_EXTENSIBILITY_MEGA_BATCH_V1

## Operating rule

Every major Workspace Manager batch advances three tracks together:

1. PRODUCT_UI
2. ENGINEERING_GOVERNANCE
3. EXTENSIBILITY

No track may starve another.

## Product slice

- `/tasks` becomes the Remote-first Engineering Task Board.
- `/extensions` becomes the Extensions Center for Skills, Agents, Tools, and Providers.
- The existing operational surfaces remain available in source while the product cutover proceeds.

## Engineering slice

Remote-first task state is explicit and machine-readable:

- `base_sha`
- `integrated_head_at_creation`
- `task_branch`
- `latest_remote_task_sha`
- `owner_id`
- `actor_id`
- `actor_type`
- `provider_id`
- `scope_patterns`
- `depends_on`
- `dependency_mode`
- `wip_checkpoint_status`
- `integration_status`

A WIP remote checkpoint is resumable work, not accepted integrated code.

## Extensibility slice

The Workspace owns registries for:

- Skills
- Agents
- Tools
- Model/Reasoning Providers

Admission is fail-closed:

`DISCOVERED -> QUARANTINED -> REVIEW -> SANDBOX -> APPROVED -> INSTALLED -> HEALTH_MONITORED`

The first foundation deliberately stops newly registered external extensions at `QUARANTINED`.

## Open-source policy

`OPEN_SOURCE_FIRST=true`
`OPEN_SOURCE_ONLY=false`

When license and capability permit, forkable, inspectable, locally hostable components are preferred.
No external framework, agent runtime, model provider, or tool becomes the Workspace authority.

## Authority

- GitHub remote task branch = authoritative WIP state.
- Integrated accepted head = authoritative integrated development state.
- Google Drive = sovereign governance/evidence record.
- Local worktree = disposable execution cache.
- Human governance remains ultimate authority.
