from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.contract_version_registry import ContractVersionRegistryV1
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.material_change_event_registry import (
    MaterialChangeEventType,
    MaterialChangeEventV1,
)
from palwakf_orchestrator.project_change_inbox import (
    ProjectChangeInboxSnapshotV1,
    ProjectChangeInboxStatus,
)
from palwakf_orchestrator.typed_dependency_graph import TypedDependencyGraphV1


class ImpactClassification(StrEnum):
    blocking = "BLOCKING"
    revalidation = "REVALIDATION"
    deferred = "DEFERRED"
    info = "INFO"
    no_impact = "NO_IMPACT"


class ProjectImpactDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=3, max_length=128)
    classification: ImpactClassification
    reason: str = Field(min_length=1, max_length=500)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)


class ImpactAnalysisV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1, max_length=200)
    authority_reference: str = Field(min_length=1, max_length=500)
    dependency_graph_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    contract_registry_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime
    decisions: tuple[ProjectImpactDecisionV1, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_decisions(self) -> Self:
        ids = [item.project_id for item in self.decisions]
        if len(set(ids)) != len(ids):
            raise ValueError("IMPACT_ANALYSIS_DUPLICATE_PROJECT_DECISION")
        return self

    def decision_for(self, project_id: str) -> ProjectImpactDecisionV1:
        for item in self.decisions:
            if item.project_id == project_id:
                return item
        raise GovernanceError("IMPACT_ANALYSIS_PROJECT_NOT_FOUND")

    @property
    def blocking_project_ids(self) -> tuple[str, ...]:
        return tuple(
            item.project_id
            for item in self.decisions
            if item.classification == ImpactClassification.blocking
        )

    @property
    def revalidation_project_ids(self) -> tuple[str, ...]:
        return tuple(
            item.project_id
            for item in self.decisions
            if item.classification == ImpactClassification.revalidation
        )


class ImpactRevalidationReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    event_id: str = Field(min_length=1, max_length=200)
    project_id: str = Field(min_length=3, max_length=128)
    authority_reference: str = Field(min_length=1, max_length=500)
    evidence: tuple[str, ...] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if any(not item.strip() for item in self.evidence):
            raise ValueError("IMPACT_REVALIDATION_EVIDENCE_REQUIRED")
        return self


def _inbox_status(
    inbox: ProjectChangeInboxSnapshotV1 | None,
    event_id: str,
    project_id: str,
) -> ProjectChangeInboxStatus | None:
    if inbox is None:
        return None
    for item in inbox.items:
        if item.event_id == event_id and item.project_id == project_id:
            return item.status
    return None


def _classify_direct(
    event: MaterialChangeEventV1,
    project_id: str,
    contract_registry: ContractVersionRegistryV1,
    inbox: ProjectChangeInboxSnapshotV1 | None,
) -> tuple[ImpactClassification, str]:
    status = _inbox_status(inbox, event.event_id, project_id)
    if status == ProjectChangeInboxStatus.resolved:
        return ImpactClassification.info, "INBOX_ITEM_RESOLVED"
    if status == ProjectChangeInboxStatus.deferred:
        return ImpactClassification.deferred, "INBOX_ITEM_DEFERRED"
    if status == ProjectChangeInboxStatus.revalidation_required:
        return ImpactClassification.revalidation, "INBOX_REVALIDATION_REQUIRED"
    if event.event_type in {
        MaterialChangeEventType.contract_version_retired,
        MaterialChangeEventType.project_boundary_changed,
    }:
        return ImpactClassification.blocking, f"DIRECT_{event.event_type.value}"
    if event.event_type == MaterialChangeEventType.contract_version_deprecated:
        return ImpactClassification.deferred, "DIRECT_CONTRACT_VERSION_DEPRECATED"
    if event.event_type in {
        MaterialChangeEventType.dependency_changed,
        MaterialChangeEventType.runtime_contract_changed,
    }:
        return ImpactClassification.revalidation, f"DIRECT_{event.event_type.value}"
    if event.event_type == MaterialChangeEventType.contract_version_published:
        if event.edge_id is not None and contract_registry.requires_revalidation(event.edge_id):
            return ImpactClassification.revalidation, "BREAKING_CONTRACT_VERSION_PUBLISHED"
        return ImpactClassification.info, "COMPATIBLE_CONTRACT_VERSION_PUBLISHED"
    return ImpactClassification.info, "DIRECT_MATERIAL_CHANGE"


def _downstream_projects(
    graph: TypedDependencyGraphV1,
    seeds: set[str],
) -> set[str]:
    downstream: set[str] = set()
    frontier = list(seeds)
    while frontier:
        producer = frontier.pop()
        for edge in graph.outgoing(producer):
            consumer = edge.consumer_project_id
            if consumer in seeds or consumer in downstream:
                continue
            downstream.add(consumer)
            frontier.append(consumer)
    return downstream


def analyze_cross_project_impact(
    *,
    event: MaterialChangeEventV1,
    graph: TypedDependencyGraphV1,
    contract_registry: ContractVersionRegistryV1,
    inbox: ProjectChangeInboxSnapshotV1 | None = None,
    generated_at: datetime | None = None,
) -> ImpactAnalysisV1:
    if event.dependency_graph_sha256 != graph.graph_sha256:
        raise GovernanceError("IMPACT_ANALYSIS_GRAPH_SNAPSHOT_MISMATCH")
    if event.contract_registry_sha256 != contract_registry.registry_sha256:
        raise GovernanceError("IMPACT_ANALYSIS_CONTRACT_SNAPSHOT_MISMATCH")
    if contract_registry.dependency_graph_sha256 != graph.graph_sha256:
        raise GovernanceError("IMPACT_ANALYSIS_REGISTRY_GRAPH_MISMATCH")

    projects = set(graph.project_ids)
    direct = set(event.affected_project_ids)
    if event.project_id not in projects or not direct.issubset(projects):
        raise GovernanceError("IMPACT_ANALYSIS_PROJECT_BINDING_MISMATCH")
    downstream = _downstream_projects(graph, direct)
    evidence = (f"material-event:{event.event_sha256}", f"change:{event.change_id}")
    decisions: list[ProjectImpactDecisionV1] = []
    for project_id in graph.project_ids:
        if project_id == event.project_id:
            classification, reason = ImpactClassification.info, "SOURCE_PROJECT_CHANGE_OWNER"
        elif project_id in direct:
            classification, reason = _classify_direct(event, project_id, contract_registry, inbox)
        elif project_id in downstream:
            classification, reason = ImpactClassification.info, "TRANSITIVE_DOWNSTREAM_VISIBILITY"
        else:
            classification, reason = (
                ImpactClassification.no_impact,
                "NO_DEPENDENCY_PATH_FROM_CHANGE",
            )
        decisions.append(
            ProjectImpactDecisionV1(
                project_id=project_id,
                classification=classification,
                reason=reason,
                evidence=evidence,
            )
        )
    return ImpactAnalysisV1(
        event_id=event.event_id,
        authority_reference=event.authority_reference,
        dependency_graph_sha256=graph.graph_sha256,
        contract_registry_sha256=contract_registry.registry_sha256,
        generated_at=generated_at or datetime.now(UTC),
        decisions=tuple(decisions),
    )


def require_project_clear_for_execution(
    analysis: ImpactAnalysisV1,
    *,
    project_id: str,
    revalidation_receipt: ImpactRevalidationReceiptV1 | None = None,
) -> ProjectImpactDecisionV1:
    decision = analysis.decision_for(project_id)
    if decision.classification == ImpactClassification.blocking:
        raise GovernanceError("IMPACT_ANALYSIS_PROJECT_BLOCKED")
    if decision.classification != ImpactClassification.revalidation:
        return decision
    if revalidation_receipt is None:
        raise GovernanceError("IMPACT_ANALYSIS_REVALIDATION_RECEIPT_REQUIRED")
    if revalidation_receipt.event_id != analysis.event_id:
        raise GovernanceError("IMPACT_ANALYSIS_REVALIDATION_EVENT_MISMATCH")
    if revalidation_receipt.project_id != project_id:
        raise GovernanceError("IMPACT_ANALYSIS_REVALIDATION_PROJECT_MISMATCH")
    if revalidation_receipt.authority_reference != analysis.authority_reference:
        raise GovernanceError("IMPACT_ANALYSIS_REVALIDATION_AUTHORITY_MISMATCH")
    return decision
