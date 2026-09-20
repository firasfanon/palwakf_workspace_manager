from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore

CENSUS_STATE_KEY = "pre_l5_agent_census_registry_v1"


class AgentRegistrySourceClass(StrEnum):
    current_role_registry = "CURRENT_ROLE_REGISTRY"
    current_runtime_registry = "CURRENT_RUNTIME_PROFILE_REGISTRY"
    current_projection = "CURRENT_ROLE_RUNTIME_PROJECTION"
    legacy_role_registry = "LEGACY_ROLE_REGISTRY"
    legacy_partial_assignments = "LEGACY_PARTIAL_ASSIGNMENTS"
    reference_workflow = "REFERENCE_WORKFLOW"
    reference_tool_catalog = "REFERENCE_TOOL_CATALOG"


class RuntimeProfileAdmission(StrEnum):
    prepare_only = "ADMITTED_PREPARE_ONLY"
    operational = "ADMITTED_OPERATIONAL"


class AgenticLineageRef(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ref_name: str = Field(min_length=1, max_length=240)
    commit_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    classification: Literal["CANONICAL_MAIN", "WIP_DIVERGED"]


class AgenticSourceLineageV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    repository: Literal["firasfanon/palwakf_agenticAi_system"] = (
        "firasfanon/palwakf_agenticAi_system"
    )
    canonical_main_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    refs: tuple[AgenticLineageRef, ...] = Field(min_length=1)
    registry_content_equivalent_across_refs: bool
    runtime_lineage_diverged: bool
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_refs(self) -> Self:
        mains = [item for item in self.refs if item.classification == "CANONICAL_MAIN"]
        if len(mains) != 1 or mains[0].commit_sha != self.canonical_main_sha:
            raise ValueError("AGENT_CENSUS_CANONICAL_MAIN_REF_MISMATCH")
        if len({item.ref_name for item in self.refs}) != len(self.refs):
            raise ValueError("AGENT_CENSUS_DUPLICATE_LINEAGE_REF")
        if not self.registry_content_equivalent_across_refs:
            raise ValueError("AGENT_CENSUS_REGISTRY_CONTENT_DRIFT_REQUIRES_RECONCILIATION")
        return self


class AgentRegistrySourceRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1, max_length=160)
    path: str = Field(min_length=1, max_length=500)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    classification: AgentRegistrySourceClass
    observed_at: datetime
    notes: tuple[str, ...] = ()


class RuntimeProfileRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str = Field(min_length=1, max_length=160)
    source_path: str = Field(min_length=1, max_length=500)
    execution_mode: str = Field(min_length=1, max_length=160)
    admission: RuntimeProfileAdmission
    output_authority: str = Field(min_length=1, max_length=160)
    capabilities: tuple[str, ...] = Field(min_length=1)
    human_review_required: bool = True


class SpecializedAgentRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_id: str = Field(min_length=1, max_length=160)
    role_id: str = Field(min_length=1, max_length=160)
    role_source_status: str = Field(min_length=1, max_length=160)
    runtime_profile_id: str = Field(min_length=1, max_length=160)
    skill_ids: tuple[str, ...] = Field(min_length=1)
    tool_bindings: tuple[str, ...] = Field(min_length=1)
    task_classes: tuple[str, ...] = Field(min_length=1)
    technical_runnable: bool
    operational_admitted: bool = False
    operational_admission_reference: str | None = None
    self_authorization_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_admission(self) -> Self:
        pending = {
            "admission_required_v2",
            "disabled_pending_admission",
            "blocked",
            "admission_pending",
        }
        if self.role_source_status in pending and self.operational_admitted:
            raise ValueError("AGENT_CENSUS_PENDING_ROLE_CANNOT_BE_OPERATIONALLY_ADMITTED")
        if self.operational_admitted and not self.operational_admission_reference:
            raise ValueError("AGENT_CENSUS_OPERATIONAL_ADMISSION_REFERENCE_REQUIRED")
        if not self.operational_admitted and self.operational_admission_reference is not None:
            raise ValueError("AGENT_CENSUS_NON_ADMITTED_ROLE_HAS_ADMISSION_REFERENCE")
        return self


class WorkflowReferenceRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: str = Field(min_length=1, max_length=200)
    source_path: str = Field(min_length=1, max_length=500)
    mode: str = Field(min_length=1, max_length=200)
    runtime_execution_allowed: Literal[False] = False


class ToolCandidateRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_id: str = Field(min_length=1, max_length=160)
    decision: str = Field(min_length=1, max_length=200)
    integration_mode: str = Field(min_length=1, max_length=200)
    operationally_admitted: Literal[False] = False


class AgentCensusSnapshotV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    registry_id: Literal["PALWAKF_AGENT_CENSUS_REGISTRY_V1"] = "PALWAKF_AGENT_CENSUS_REGISTRY_V1"
    source_authority: Literal["WORKSPACE_DRIVE_SOVEREIGN"] = "WORKSPACE_DRIVE_SOVEREIGN"
    runtime_role: Literal["GOVERNED_PROJECTION_ONLY"] = "GOVERNED_PROJECTION_ONLY"
    source_revision: str = Field(min_length=1, max_length=500)
    observed_at: datetime
    lineage: AgenticSourceLineageV1
    sources: tuple[AgentRegistrySourceRecordV1, ...] = Field(min_length=1)
    runtime_profiles: tuple[RuntimeProfileRecordV1, ...] = Field(min_length=1)
    agents: tuple[SpecializedAgentRecordV1, ...] = Field(min_length=1)
    workflows: tuple[WorkflowReferenceRecordV1, ...] = ()
    tool_candidates: tuple[ToolCandidateRecordV1, ...] = ()
    census_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        source_ids = [item.source_id for item in self.sources]
        source_paths = [item.path for item in self.sources]
        if len(set(source_ids)) != len(source_ids) or len(set(source_paths)) != len(source_paths):
            raise ValueError("AGENT_CENSUS_DUPLICATE_SOURCE")
        required = {
            AgentRegistrySourceClass.current_role_registry,
            AgentRegistrySourceClass.current_runtime_registry,
            AgentRegistrySourceClass.current_projection,
            AgentRegistrySourceClass.legacy_role_registry,
        }
        present = {item.classification for item in self.sources}
        if not required.issubset(present):
            raise ValueError("AGENT_CENSUS_REQUIRED_SOURCE_CLASSIFICATION_MISSING")
        if (
            sum(
                item.classification == AgentRegistrySourceClass.current_role_registry
                for item in self.sources
            )
            != 1
        ):
            raise ValueError("AGENT_CENSUS_CURRENT_ROLE_REGISTRY_MUST_BE_UNIQUE")

        profile_ids = [item.profile_id for item in self.runtime_profiles]
        if len(set(profile_ids)) != len(profile_ids):
            raise ValueError("AGENT_CENSUS_DUPLICATE_RUNTIME_PROFILE")
        agent_ids = [item.agent_id for item in self.agents]
        role_ids = [item.role_id for item in self.agents]
        if len(set(agent_ids)) != len(agent_ids) or len(set(role_ids)) != len(role_ids):
            raise ValueError("AGENT_CENSUS_DUPLICATE_SPECIALIZED_AGENT")
        known_profiles = set(profile_ids)
        if any(item.runtime_profile_id not in known_profiles for item in self.agents):
            raise ValueError("AGENT_CENSUS_UNKNOWN_RUNTIME_PROFILE")
        workflow_ids = [item.workflow_id for item in self.workflows]
        tool_ids = [item.tool_id for item in self.tool_candidates]
        if len(set(workflow_ids)) != len(workflow_ids):
            raise ValueError("AGENT_CENSUS_DUPLICATE_WORKFLOW")
        if len(set(tool_ids)) != len(tool_ids):
            raise ValueError("AGENT_CENSUS_DUPLICATE_TOOL_CANDIDATE")
        return self

    def get_agent(self, agent_id: str) -> SpecializedAgentRecordV1:
        for agent in self.agents:
            if agent.agent_id == agent_id:
                return agent
        raise GovernanceError("AGENT_CENSUS_AGENT_NOT_FOUND")

    def assert_operationally_admitted(self, agent_id: str) -> SpecializedAgentRecordV1:
        agent = self.get_agent(agent_id)
        if not agent.operational_admitted:
            raise GovernanceError("AGENT_NOT_OPERATIONALLY_ADMITTED")
        return agent

    def shared_runtime_profiles(self) -> dict[str, tuple[str, ...]]:
        grouped: dict[str, list[str]] = {}
        for agent in self.agents:
            grouped.setdefault(agent.runtime_profile_id, []).append(agent.role_id)
        return {
            profile_id: tuple(sorted(role_ids))
            for profile_id, role_ids in grouped.items()
            if len(role_ids) > 1
        }

    @property
    def unique_skill_ids(self) -> tuple[str, ...]:
        return tuple(sorted({skill for agent in self.agents for skill in agent.skill_ids}))


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _snapshot_payload(snapshot: AgentCensusSnapshotV1 | dict[str, object]) -> dict[str, object]:
    payload = (
        snapshot.model_dump(mode="json")
        if isinstance(snapshot, AgentCensusSnapshotV1)
        else dict(snapshot)
    )
    payload.pop("census_sha256", None)
    return payload


def build_agent_census_snapshot(
    *,
    source_revision: str,
    lineage: AgenticSourceLineageV1,
    sources: tuple[AgentRegistrySourceRecordV1, ...],
    runtime_profiles: tuple[RuntimeProfileRecordV1, ...],
    agents: tuple[SpecializedAgentRecordV1, ...],
    workflows: tuple[WorkflowReferenceRecordV1, ...] = (),
    tool_candidates: tuple[ToolCandidateRecordV1, ...] = (),
    observed_at: datetime | None = None,
) -> AgentCensusSnapshotV1:
    timestamp = observed_at or datetime.now(UTC)
    payload: dict[str, object] = {
        "registry_id": "PALWAKF_AGENT_CENSUS_REGISTRY_V1",
        "source_authority": "WORKSPACE_DRIVE_SOVEREIGN",
        "runtime_role": "GOVERNED_PROJECTION_ONLY",
        "source_revision": source_revision,
        "observed_at": timestamp,
        "lineage": lineage.model_dump(mode="json"),
        "sources": [item.model_dump(mode="json") for item in sources],
        "runtime_profiles": [item.model_dump(mode="json") for item in runtime_profiles],
        "agents": [item.model_dump(mode="json") for item in agents],
        "workflows": [item.model_dump(mode="json") for item in workflows],
        "tool_candidates": [item.model_dump(mode="json") for item in tool_candidates],
        "canonical_promotion_allowed": False,
    }
    provisional = AgentCensusSnapshotV1.model_validate({**payload, "census_sha256": "0" * 64})
    normalized = _snapshot_payload(provisional)
    return AgentCensusSnapshotV1.model_validate(
        {**normalized, "census_sha256": _sha256(normalized)}
    )


class AgentCensusRegistryStore:
    def __init__(
        self,
        state_store: StateStore,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._state_store = state_store
        self._now = now or (lambda: datetime.now(UTC))

    def history(self) -> tuple[AgentCensusSnapshotV1, ...]:
        state = self._state_store.load()
        raw = state.get(CENSUS_STATE_KEY, {})
        values = raw.get("snapshots", []) if isinstance(raw, dict) else []
        snapshots: list[AgentCensusSnapshotV1] = []
        for item in values:
            snapshot = AgentCensusSnapshotV1.model_validate(item)
            if snapshot.census_sha256 != _sha256(_snapshot_payload(snapshot)):
                raise GovernanceError("AGENT_CENSUS_HASH_MISMATCH")
            snapshots.append(snapshot)
        return tuple(snapshots)

    def current(self) -> AgentCensusSnapshotV1:
        history = self.history()
        if not history:
            raise GovernanceError("AGENT_CENSUS_NOT_IMPORTED")
        return history[-1]

    def import_snapshot(
        self,
        *,
        source_revision: str,
        lineage: AgenticSourceLineageV1,
        sources: tuple[AgentRegistrySourceRecordV1, ...],
        runtime_profiles: tuple[RuntimeProfileRecordV1, ...],
        agents: tuple[SpecializedAgentRecordV1, ...],
        workflows: tuple[WorkflowReferenceRecordV1, ...] = (),
        tool_candidates: tuple[ToolCandidateRecordV1, ...] = (),
    ) -> AgentCensusSnapshotV1:
        snapshot = build_agent_census_snapshot(
            source_revision=source_revision,
            lineage=lineage,
            sources=sources,
            runtime_profiles=runtime_profiles,
            agents=agents,
            workflows=workflows,
            tool_candidates=tool_candidates,
            observed_at=self._now(),
        )
        history = list(self.history())
        for existing in history:
            if existing.source_revision != source_revision:
                continue
            if existing.census_sha256 != snapshot.census_sha256:
                raise GovernanceError("AGENT_CENSUS_SOURCE_REVISION_CONFLICT")
            return existing

        history.append(snapshot)
        state = self._state_store.load()
        state[CENSUS_STATE_KEY] = {
            "registry_version": "PALWAKF_AGENT_CENSUS_REGISTRY_V1",
            "source_of_truth": "WORKSPACE_DRIVE_SOVEREIGN",
            "runtime_role": "GOVERNED_PROJECTION_ONLY",
            "snapshots": [item.model_dump(mode="json") for item in history],
        }
        self._state_store.save(state)
        return snapshot
