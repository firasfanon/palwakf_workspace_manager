from palwakf_orchestrator.engineering_os_contracts import (
    ActorType,
    CreateEngineeringTaskRequest,
    DependencyMode,
    ExtensionKind,
    ExtensionSourceKind,
    RegisterExtensionRequest,
    RemoteCheckpointRequest,
)
from palwakf_orchestrator.engineering_os_service import EngineeringOsService
from palwakf_orchestrator.persistence import MemoryStateStore

HEAD = "a" * 40


def task_request() -> CreateEngineeringTaskRequest:
    return CreateEngineeringTaskRequest(
        task_id="WM-101",
        project_id="PALWAKF_WORKSPACE_MANAGER",
        title="Remote first task",
        description="Build a visible remote-first task slice.",
        repository="firasfanon/palwakf_workspace_manager",
        base_sha=HEAD,
        task_branch="task/WM-101",
        owner_id="firas",
        actor_id="firas",
        actor_type=ActorType.human,
        scope_patterns=["lib/**"],
        depends_on=[],
        dependency_mode=DependencyMode.independent,
        required_capabilities=["source.control"],
        required_tests=["targeted"],
    )


def test_remote_first_task_and_checkpoint() -> None:
    service = EngineeringOsService(MemoryStateStore())

    created = service.create_task(task_request())
    assert created.base_sha == HEAD
    assert created.task_branch == "task/WM-101"
    assert created.status.value == "READY"
    assert created.latest_remote_task_sha is None

    checkpointed = service.checkpoint_task(
        created.task_id,
        RemoteCheckpointRequest(
            remote_sha="b" * 40,
            evidence=["github:task/WM-101"],
        ),
    )
    assert checkpointed.status.value == "WIP_REMOTE_CHECKPOINTED"
    assert checkpointed.latest_remote_task_sha == "b" * 40
    assert checkpointed.wip_checkpoint_status == "REMOTE_CHECKPOINTED"


def test_extension_enters_quarantine_and_summary_counts() -> None:
    service = EngineeringOsService(MemoryStateStore())
    service.create_task(task_request())

    extension = service.register_extension(
        RegisterExtensionRequest(
            extension_id="skill.example",
            kind=ExtensionKind.skill,
            name="Example Skill",
            version="1.0.0",
            source_kind=ExtensionSourceKind.github,
            source_reference="example/skill",
            open_source=True,
            license="MIT",
            capabilities=["source.analysis"],
            declared_roles=["knowledge.skill"],
            required_permissions=["read"],
            allowed_projects=["PALWAKF_WORKSPACE_MANAGER"],
        )
    )

    assert extension.lifecycle.value == "QUARANTINED"
    assert extension.declared_roles == ["knowledge.skill"]
    assert extension.role_authorities["knowledge.skill"].value == "NOT_AUTHORIZED"
    summary = service.summary()
    assert summary.tasks_by_status["READY"] == 1
    assert summary.extensions_by_kind["SKILL"] == 1
    assert summary.quarantined_extensions == 1


def test_local_assistant_and_alternate_provider_enter_quarantine_without_authority() -> None:
    service = EngineeringOsService(MemoryStateStore())

    local_agent = service.register_extension(
        RegisterExtensionRequest(
            extension_id="agent.local.example",
            kind=ExtensionKind.agent,
            name="Local Assistant Example",
            version="0.1.0",
            source_kind=ExtensionSourceKind.local,
            source_reference="local://agent/example",
            open_source=True,
            license="MIT",
            capabilities=["reasoning", "test.execution"],
            declared_roles=["reasoning", "test_execution"],
        )
    )
    provider = service.register_extension(
        RegisterExtensionRequest(
            extension_id="provider.alt.example",
            kind=ExtensionKind.provider,
            name="Alternate Reasoning Provider",
            version="0.1.0",
            source_kind=ExtensionSourceKind.api,
            source_reference="provider://alternate",
            open_source=False,
            capabilities=["reasoning"],
            declared_roles=["reasoning"],
        )
    )

    assert local_agent.lifecycle.value == "QUARANTINED"
    assert provider.lifecycle.value == "QUARANTINED"
    assert local_agent.role_authorities["reasoning"].value == "NOT_AUTHORIZED"
    assert local_agent.role_authorities["test_execution"].value == "NOT_AUTHORIZED"
    assert provider.role_authorities["reasoning"].value == "NOT_AUTHORIZED"
