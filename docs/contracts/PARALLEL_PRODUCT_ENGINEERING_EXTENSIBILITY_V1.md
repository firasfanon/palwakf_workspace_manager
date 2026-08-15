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


## Provider-role and model-neutral authority

`PROVIDER_LOCK_IN=false`
`MODEL_LOCK_IN=false`
`EXECUTOR_LOCK_IN=false`
`SKILL_SOURCE_LOCK_IN=false`

The Workspace distinguishes presence from authority. Provider and tool state is
role-specific rather than binary:

- installed/present
- autonomous development authority
- governed patch-relay authority
- Git transport authority
- reasoning-provider authority
- operational health

Codex is currently one governed executor adapter. Autonomous development,
independent debugging and architecture decisions are suspended, while governed
patch relay and Git transport remain authorized only inside explicit governed
scope.

`code.execution` is reserved for autonomous code execution and fails closed
until an explicitly authorized autonomous executor exists.
`governed.patch_relay` is a separate capability and may be satisfied by Codex
or a future approved executor.

External Skills, Agents/local assistants, Tools, and Providers may declare
roles and capabilities at registration, but quarantine grants no execution
authority. Effective role authority remains `NOT_AUTHORIZED` until a later
governance approval stage. `Skill != Tool`, `Agent != Provider`, and provider
presence never implies execution authority.

The current OpenAI Agents planner and Codex SDK/MCP gateways are default
adapters, not permanent platform authorities. Generic reasoning/executor
contract fields must coexist with legacy compatibility aliases during migration.
