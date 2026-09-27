from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.environment_runtime_registry import (
    EnvironmentRuntimeRegistrySnapshotV1,
    project_runtime_components,
)
from palwakf_orchestrator.errors import GovernanceError


class RuntimeComponentLifecycle(StrEnum):
    discovered = "DISCOVERED"
    probed = "PROBED"
    healthy = "HEALTHY"
    degraded = "DEGRADED"
    unavailable = "UNAVAILABLE"
    quarantined = "QUARANTINED"
    stopped = "STOPPED"


class RuntimeSupervisorAction(StrEnum):
    probe = "PROBE"
    start = "START"
    stop = "STOP"
    restart = "RESTART"
    recover = "RECOVER"
    resume = "RESUME"


MUTATING_RUNTIME_ACTIONS = frozenset(
    {
        RuntimeSupervisorAction.start,
        RuntimeSupervisorAction.stop,
        RuntimeSupervisorAction.restart,
        RuntimeSupervisorAction.recover,
        RuntimeSupervisorAction.resume,
    }
)


class RuntimeComponentSpecV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{1,79}$")
    dependencies: tuple[str, ...] = ()
    critical: bool = False
    expected_version: str | None = Field(default=None, max_length=160)
    allowed_actions: tuple[RuntimeSupervisorAction, ...] = (
        RuntimeSupervisorAction.probe,
    )
    bounded_command_ids: dict[RuntimeSupervisorAction, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_spec(self) -> RuntimeComponentSpecV1:
        if self.component_id in self.dependencies:
            raise ValueError("RUNTIME_COMPONENT_SELF_DEPENDENCY")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("RUNTIME_COMPONENT_DUPLICATE_DEPENDENCY")
        allowed = set(self.allowed_actions)
        if any(action not in allowed for action in self.bounded_command_ids):
            raise ValueError("RUNTIME_COMMAND_BINDING_FOR_DISALLOWED_ACTION")
        if any(not command_id.strip() for command_id in self.bounded_command_ids.values()):
            raise ValueError("RUNTIME_BOUNDED_COMMAND_ID_MUST_BE_NONEMPTY")
        return self


class RuntimeComponentObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    component_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{1,79}$")
    lifecycle_state: RuntimeComponentLifecycle
    version: str | None = Field(default=None, max_length=160)
    process_name: str | None = Field(default=None, max_length=160)
    process_present: bool | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    port_listening: bool | None = None
    observed_at: datetime
    evidence: tuple[str, ...] = Field(default_factory=tuple, max_length=64)

    @model_validator(mode="after")
    def validate_observation(self) -> RuntimeComponentObservationV1:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("RUNTIME_OBSERVATION_EVIDENCE_MUST_BE_NONEMPTY")
        if self.lifecycle_state == RuntimeComponentLifecycle.healthy:
            if self.process_present is False or self.port_listening is False:
                raise ValueError("HEALTHY_RUNTIME_CANNOT_HAVE_NEGATIVE_PROCESS_OR_PORT")
        return self


class RuntimeSupervisorActionRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str = Field(min_length=1, max_length=160)
    correlation_id: str = Field(min_length=1, max_length=160)
    component_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{1,79}$")
    action: RuntimeSupervisorAction
    authority_reference: str = Field(min_length=1, max_length=500)
    explicit_authorization: bool = False
    environment: Literal["local"] = "local"
    production: Literal[False] = False


class RuntimeSupervisorActionPlanV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    request_id: str
    correlation_id: str
    component_id: str
    action: RuntimeSupervisorAction
    allowed: bool
    dependency_order: tuple[str, ...]
    execution_channel: Literal["PALWAKF_SECURE_MCP_BOUNDED_POWERSHELL"]
    bounded_command_id: str | None
    blockers: tuple[str, ...]
    no_authority_expansion: Literal[True] = True


class ProviderRuntimeProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    compatibility_version: Literal["1"] = "1"
    contract_type: Literal["ProviderDescriptor"] = "ProviderDescriptor"
    project_id: str = Field(min_length=1, max_length=160)
    task_id: str = Field(min_length=1, max_length=160)
    correlation_id: str = Field(min_length=1, max_length=160)
    authority_scope: Literal["NO_SOVEREIGN_AUTHORITY"] = "NO_SOVEREIGN_AUTHORITY"
    producer: Literal["Agentic"] = "Agentic"
    created_at: datetime
    provenance: tuple[str, ...] = Field(min_length=1, max_length=64)
    provider_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{1,79}$")
    provider_kind: Literal[
        "MODEL_RUNTIME",
        "GENERAL_AGENT",
        "ENGINEERING",
        "BROWSER_UAT",
    ] = "ENGINEERING"
    version: str | None = Field(default=None, max_length=160)
    endpoint: str | None = Field(default=None, max_length=500)
    lifecycle: Literal["DISCOVERED", "PROBED", "BENCHMARKED", "ADMITTED"]
    health: Literal["HEALTHY", "DEGRADED", "UNAVAILABLE", "QUARANTINED"]
    capabilities: tuple[str, ...]
    admitted_capabilities: tuple[str, ...] = ()
    read_write_class: Literal[
        "MODEL_INFERENCE",
        "READ_ONLY",
        "BOUNDED_WRITE_CAPABLE",
        "BROWSER_UAT",
    ] = "READ_ONLY"
    bounded_write_admitted: bool = False
    admission_evidence: tuple[str, ...] = ()
    route_eligible: bool

    @model_validator(mode="after")
    def validate_route_eligibility(self) -> ProviderRuntimeProjectionV1:
        if self.route_eligible and not (
            self.lifecycle == "ADMITTED" and self.health == "HEALTHY"
        ):
            raise ValueError("ROUTE_ELIGIBLE_PROVIDER_MUST_BE_ADMITTED_AND_HEALTHY")
        return self


class RuntimeSupervisorSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    compatibility_version: Literal["1"] = "1"
    contract_type: Literal["RuntimeHealth"] = "RuntimeHealth"
    observed_at: datetime
    components: tuple[RuntimeComponentObservationV1, ...]
    dependency_order: tuple[str, ...]
    overall_health: Literal["HEALTHY", "DEGRADED", "UNAVAILABLE"]
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)


_ALLOWED_TRANSITIONS: dict[
    RuntimeComponentLifecycle,
    frozenset[RuntimeComponentLifecycle],
] = {
    RuntimeComponentLifecycle.discovered: frozenset(
        {RuntimeComponentLifecycle.probed, RuntimeComponentLifecycle.quarantined}
    ),
    RuntimeComponentLifecycle.probed: frozenset(
        {
            RuntimeComponentLifecycle.healthy,
            RuntimeComponentLifecycle.degraded,
            RuntimeComponentLifecycle.unavailable,
            RuntimeComponentLifecycle.quarantined,
        }
    ),
    RuntimeComponentLifecycle.healthy: frozenset(
        {
            RuntimeComponentLifecycle.degraded,
            RuntimeComponentLifecycle.unavailable,
            RuntimeComponentLifecycle.quarantined,
            RuntimeComponentLifecycle.stopped,
        }
    ),
    RuntimeComponentLifecycle.degraded: frozenset(
        {
            RuntimeComponentLifecycle.healthy,
            RuntimeComponentLifecycle.unavailable,
            RuntimeComponentLifecycle.quarantined,
            RuntimeComponentLifecycle.stopped,
        }
    ),
    RuntimeComponentLifecycle.unavailable: frozenset(
        {
            RuntimeComponentLifecycle.probed,
            RuntimeComponentLifecycle.quarantined,
            RuntimeComponentLifecycle.stopped,
        }
    ),
    RuntimeComponentLifecycle.quarantined: frozenset({RuntimeComponentLifecycle.probed}),
    RuntimeComponentLifecycle.stopped: frozenset(
        {RuntimeComponentLifecycle.probed, RuntimeComponentLifecycle.quarantined}
    ),
}


def transition_runtime_component(
    current: RuntimeComponentLifecycle,
    target: RuntimeComponentLifecycle,
    *,
    readmission_authorized: bool = False,
) -> RuntimeComponentLifecycle:
    if target == current:
        return current
    if current == RuntimeComponentLifecycle.quarantined and not readmission_authorized:
        raise GovernanceError("RUNTIME_COMPONENT_READMISSION_AUTHORIZATION_REQUIRED")
    if target not in _ALLOWED_TRANSITIONS[current]:
        raise GovernanceError(f"INVALID_RUNTIME_COMPONENT_TRANSITION:{current}:{target}")
    return target


class RuntimeSupervisorV1:
    def __init__(self, specs: Iterable[RuntimeComponentSpecV1]) -> None:
        items = tuple(specs)
        self._specs = {item.component_id: item for item in items}
        if len(self._specs) != len(items):
            raise GovernanceError("DUPLICATE_RUNTIME_COMPONENT_ID")
        self._validate_dependencies()
        self._dependency_order = self._topological_order()

    @property
    def dependency_order(self) -> tuple[str, ...]:
        return self._dependency_order

    def _validate_dependencies(self) -> None:
        known = set(self._specs)
        for spec in self._specs.values():
            missing = [dep for dep in spec.dependencies if dep not in known]
            if missing:
                raise GovernanceError(
                    f"RUNTIME_COMPONENT_DEPENDENCY_UNKNOWN:{spec.component_id}:{missing[0]}"
                )

    def _topological_order(self) -> tuple[str, ...]:
        visiting: set[str] = set()
        visited: set[str] = set()
        ordered: list[str] = []

        def visit(component_id: str) -> None:
            if component_id in visited:
                return
            if component_id in visiting:
                raise GovernanceError("RUNTIME_COMPONENT_DEPENDENCY_CYCLE")
            visiting.add(component_id)
            for dependency in self._specs[component_id].dependencies:
                visit(dependency)
            visiting.remove(component_id)
            visited.add(component_id)
            ordered.append(component_id)

        for component_id in sorted(self._specs):
            visit(component_id)
        return tuple(ordered)

    def reconcile(
        self,
        runtime_registry: EnvironmentRuntimeRegistrySnapshotV1,
        observations: Iterable[RuntimeComponentObservationV1],
        *,
        observed_at: datetime | None = None,
        evidence: tuple[str, ...] = ("runtime-supervisor-reconciliation",),
    ) -> RuntimeSupervisorSnapshotV1:
        registry_versions = {
            item.component_id: item.version
            for item in project_runtime_components(runtime_registry)
        }
        observation_items = tuple(observations)
        observed = {item.component_id: item for item in observation_items}
        if len(observed) != len(observation_items):
            raise GovernanceError("DUPLICATE_RUNTIME_OBSERVATION")

        reconciled: list[RuntimeComponentObservationV1] = []
        for component_id in self._dependency_order:
            spec = self._specs[component_id]
            item = observed.get(component_id)
            if item is None:
                item = RuntimeComponentObservationV1(
                    component_id=component_id,
                    lifecycle_state=RuntimeComponentLifecycle.unavailable,
                    version=registry_versions.get(component_id),
                    observed_at=observed_at or datetime.now(UTC),
                    evidence=("runtime-observation-missing",),
                )
            expected = spec.expected_version or registry_versions.get(component_id)
            if (
                expected
                and item.version
                and item.version != expected
                and item.lifecycle_state == RuntimeComponentLifecycle.healthy
            ):
                item = item.model_copy(
                    update={"lifecycle_state": RuntimeComponentLifecycle.degraded}
                )
            reconciled.append(item)

        critical = [
            item for item in reconciled if self._specs[item.component_id].critical
        ]
        overall: Literal["HEALTHY", "DEGRADED", "UNAVAILABLE"]
        if any(
            item.lifecycle_state
            in {
                RuntimeComponentLifecycle.unavailable,
                RuntimeComponentLifecycle.quarantined,
                RuntimeComponentLifecycle.stopped,
            }
            for item in critical
        ):
            overall = "UNAVAILABLE"
        elif any(
            item.lifecycle_state != RuntimeComponentLifecycle.healthy for item in critical
        ):
            overall = "DEGRADED"
        else:
            overall = "HEALTHY"

        return RuntimeSupervisorSnapshotV1(
            observed_at=observed_at or datetime.now(UTC),
            components=tuple(reconciled),
            dependency_order=self._dependency_order,
            overall_health=overall,
            evidence=evidence,
        )

    def plan_action(
        self,
        request: RuntimeSupervisorActionRequestV1,
        observations: Iterable[RuntimeComponentObservationV1],
    ) -> RuntimeSupervisorActionPlanV1:
        spec = self._specs.get(request.component_id)
        if spec is None:
            raise GovernanceError("RUNTIME_COMPONENT_UNKNOWN")

        blockers: list[str] = []
        observed = {item.component_id: item for item in observations}

        if request.action not in spec.allowed_actions:
            blockers.append("ACTION_NOT_ALLOWED_FOR_COMPONENT")
        command_id = spec.bounded_command_ids.get(request.action)
        if command_id is None:
            blockers.append("BOUNDED_COMMAND_BINDING_REQUIRED")
        if request.action in MUTATING_RUNTIME_ACTIONS and not request.explicit_authorization:
            blockers.append("EXPLICIT_AUTHORIZATION_REQUIRED")

        if request.action in {
            RuntimeSupervisorAction.start,
            RuntimeSupervisorAction.restart,
            RuntimeSupervisorAction.recover,
            RuntimeSupervisorAction.resume,
        }:
            for dependency in spec.dependencies:
                state = observed.get(dependency)
                if state is None or state.lifecycle_state != RuntimeComponentLifecycle.healthy:
                    blockers.append(f"DEPENDENCY_NOT_HEALTHY:{dependency}")

        if request.action == RuntimeSupervisorAction.stop:
            for candidate in self._specs.values():
                if request.component_id not in candidate.dependencies:
                    continue
                state = observed.get(candidate.component_id)
                if state and state.lifecycle_state in {
                    RuntimeComponentLifecycle.healthy,
                    RuntimeComponentLifecycle.degraded,
                }:
                    blockers.append(f"DEPENDENT_ACTIVE:{candidate.component_id}")

        target_order = tuple(
            component_id
            for component_id in self._dependency_order
            if component_id in {*spec.dependencies, spec.component_id}
        )
        if request.action == RuntimeSupervisorAction.stop:
            target_order = tuple(reversed(target_order))

        return RuntimeSupervisorActionPlanV1(
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            component_id=request.component_id,
            action=request.action,
            allowed=not blockers,
            dependency_order=target_order,
            execution_channel="PALWAKF_SECURE_MCP_BOUNDED_POWERSHELL",
            bounded_command_id=command_id,
            blockers=tuple(blockers),
        )


def default_runtime_component_specs_v1() -> tuple[RuntimeComponentSpecV1, ...]:
    """Accepted bootstrap graph; action bindings remain fail-closed until admitted."""

    return (
        RuntimeComponentSpecV1(component_id="meshcentral", critical=True),
        RuntimeComponentSpecV1(
            component_id="meshagent",
            dependencies=("meshcentral",),
            critical=True,
        ),
        RuntimeComponentSpecV1(
            component_id="palwakf_remote_mcp",
            dependencies=("meshagent",),
            critical=True,
        ),
        RuntimeComponentSpecV1(
            component_id="secure_tunnel",
            dependencies=("palwakf_remote_mcp",),
            critical=True,
        ),
        RuntimeComponentSpecV1(component_id="ollama"),
        RuntimeComponentSpecV1(component_id="hermes_headless"),
        RuntimeComponentSpecV1(component_id="opencode"),
        RuntimeComponentSpecV1(component_id="playwright"),
    )
