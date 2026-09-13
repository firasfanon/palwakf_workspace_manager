from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.intersystem_contracts import (
    WorkspaceAuthorityPackageV1,
)


class InstructionRecordV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction_id: str
    authority: str
    authority_rank: int = Field(ge=0)
    version: str
    effective_at: datetime

    status: Literal[
        "ACTIVE",
        "SUPERSEDED",
        "REVOKED",
        "HISTORICAL",
    ]

    source_authority: Literal[
        "WORKSPACE_DRIVE_SOVEREIGN",
        "GITHUB_CODE_AUTHORITY",
        "LOCAL_EXECUTION_EVIDENCE",
        "HANDOFF",
        "CHAT_MEMORY",
    ]

    applies_to_projects: tuple[str, ...] = ("*",)
    supersedes: tuple[str, ...] = ()

    conflict_key: str
    directive_fingerprint: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )


class InstructionExclusionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction_id: str
    reason: str


class ActiveGoverningInstructionSetV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolver_id: Literal[
        "PALWAKF_ACTIVE_INSTRUCTION_RESOLVER_V1"
    ] = "PALWAKF_ACTIVE_INSTRUCTION_RESOLVER_V1"

    resolution_status: Literal["RESOLVED"] = "RESOLVED"

    project_id: str
    task_id: str
    state_package_id: str
    authority_reference: str

    active_instructions: tuple[
        InstructionRecordV1, ...
    ]

    exclusions: tuple[
        InstructionExclusionV1, ...
    ] = ()

    resolution_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )


class PreExecutionKnowledgeGateV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    task_id: str

    active_lesson_ids: tuple[str, ...]
    known_failure_fingerprint_ids: tuple[str, ...]
    applicable_skill_ids: tuple[str, ...]
    preventive_gate_ids: tuple[str, ...]

    known_relevant_lessons_reused: Literal[True] = True


class PreL5WorkspaceBootstrapEnvelopeV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: Literal[
        "PALWAKF_PRE_L5_WORKSPACE_BOOTSTRAP_V1"
    ] = "PALWAKF_PRE_L5_WORKSPACE_BOOTSTRAP_V1"

    bootstrap_sequence: tuple[str, ...] = (
        "FRESH_RECONCILIATION",
        "ACTIVE_INSTRUCTION_RESOLUTION",
        "ACTIVE_LESSONS",
        "KNOWN_FAILURE_FINGERPRINTS",
        "APPLICABLE_SKILLS",
        "PREVENTIVE_GATES",
        "STATE_PACKAGE",
        "AUTHORIZATION_ENVELOPE",
        "EXECUTION",
    )

    authority_package: WorkspaceAuthorityPackageV1
    active_instruction_set: ActiveGoverningInstructionSetV1
    knowledge_gate: PreExecutionKnowledgeGateV1

    authority_package_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    active_instruction_set_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    execution_admission: Literal["READY"] = "READY"

    @model_validator(mode="after")
    def bind_all_authority(self):
        package = self.authority_package
        active = self.active_instruction_set
        knowledge = self.knowledge_gate

        if active.project_id != package.project_id:
            raise ValueError(
                "ACTIVE_INSTRUCTION_PROJECT_BINDING_MISMATCH"
            )

        if active.task_id != package.task_id:
            raise ValueError(
                "ACTIVE_INSTRUCTION_TASK_BINDING_MISMATCH"
            )

        if active.state_package_id != package.state_package_id:
            raise ValueError(
                "ACTIVE_INSTRUCTION_STATE_PACKAGE_BINDING_MISMATCH"
            )

        if active.authority_reference != package.authority_reference:
            raise ValueError(
                "ACTIVE_INSTRUCTION_AUTHORITY_BINDING_MISMATCH"
            )

        if knowledge.project_id != package.project_id:
            raise ValueError(
                "KNOWLEDGE_GATE_PROJECT_BINDING_MISMATCH"
            )

        if knowledge.task_id != package.task_id:
            raise ValueError(
                "KNOWLEDGE_GATE_TASK_BINDING_MISMATCH"
            )

        return self


def _canonical(value) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _sha256(value) -> str:
    return hashlib.sha256(
        _canonical(value).encode("utf-8")
    ).hexdigest()


class ActiveInstructionResolverV1:
    resolver_id = "PALWAKF_ACTIVE_INSTRUCTION_RESOLVER_V1"

    def resolve(
        self,
        *,
        project_id: str,
        task_id: str,
        state_package_id: str,
        authority_reference: str,
        records: list[InstructionRecordV1],
    ) -> ActiveGoverningInstructionSetV1:

        if not records:
            raise GovernanceError(
                "ACTIVE_INSTRUCTION_INPUT_REQUIRED"
            )

        ids = [record.instruction_id for record in records]

        if len(ids) != len(set(ids)):
            raise GovernanceError(
                "DUPLICATE_INSTRUCTION_ID"
            )

        exclusions: list[InstructionExclusionV1] = []
        candidates: list[InstructionRecordV1] = []

        for record in records:
            projects = set(record.applies_to_projects)

            if (
                "*" not in projects
                and project_id not in projects
            ):
                exclusions.append(
                    InstructionExclusionV1(
                        instruction_id=record.instruction_id,
                        reason="PROJECT_NOT_APPLICABLE",
                    )
                )
                continue

            if record.status != "ACTIVE":
                exclusions.append(
                    InstructionExclusionV1(
                        instruction_id=record.instruction_id,
                        reason=f"STATUS_{record.status}_EXCLUDED",
                    )
                )
                continue

            if (
                record.source_authority
                != "WORKSPACE_DRIVE_SOVEREIGN"
            ):
                raise GovernanceError(
                    "UNTRUSTED_ACTIVE_INSTRUCTION_SOURCE:"
                    + record.instruction_id
                )

            candidates.append(record)

        superseded_ids = {
            superseded_id
            for candidate in candidates
            for superseded_id in candidate.supersedes
        }

        remaining: list[InstructionRecordV1] = []

        for candidate in candidates:
            if candidate.instruction_id in superseded_ids:
                exclusions.append(
                    InstructionExclusionV1(
                        instruction_id=candidate.instruction_id,
                        reason="SUPERSEDED_BY_ACTIVE_INSTRUCTION",
                    )
                )
                continue

            remaining.append(candidate)

        grouped: dict[str, list[InstructionRecordV1]] = {}

        for candidate in remaining:
            grouped.setdefault(
                candidate.conflict_key,
                [],
            ).append(candidate)

        selected: list[InstructionRecordV1] = []

        for conflict_key, group in grouped.items():
            fingerprints = {
                item.directive_fingerprint
                for item in group
            }

            if len(fingerprints) > 1:
                raise GovernanceError(
                    "CONFLICTING_ACTIVE_INSTRUCTIONS:"
                    + conflict_key
                )

            ordered = sorted(
                group,
                key=lambda item: (
                    item.authority_rank,
                    item.effective_at,
                    item.version,
                    item.instruction_id,
                ),
                reverse=True,
            )

            winner = ordered[0]
            selected.append(winner)

            for redundant in ordered[1:]:
                exclusions.append(
                    InstructionExclusionV1(
                        instruction_id=redundant.instruction_id,
                        reason=(
                            "REDUNDANT_ACTIVE_INSTRUCTION_"
                            "LOWER_PRECEDENCE"
                        ),
                    )
                )

        if not selected:
            raise GovernanceError(
                "ACTIVE_GOVERNING_INSTRUCTION_SET_EMPTY"
            )

        selected = sorted(
            selected,
            key=lambda item: (
                item.conflict_key,
                item.instruction_id,
            ),
        )

        exclusions = sorted(
            exclusions,
            key=lambda item: (
                item.instruction_id,
                item.reason,
            ),
        )

        digest_payload = {
            "resolver_id": self.resolver_id,
            "project_id": project_id,
            "task_id": task_id,
            "state_package_id": state_package_id,
            "authority_reference": authority_reference,
            "active_instructions": [
                item.model_dump(mode="json")
                for item in selected
            ],
            "exclusions": [
                item.model_dump(mode="json")
                for item in exclusions
            ],
        }

        return ActiveGoverningInstructionSetV1(
            project_id=project_id,
            task_id=task_id,
            state_package_id=state_package_id,
            authority_reference=authority_reference,
            active_instructions=tuple(selected),
            exclusions=tuple(exclusions),
            resolution_sha256=_sha256(digest_payload),
        )


def build_pre_l5_bootstrap_envelope(
    *,
    authority_package: WorkspaceAuthorityPackageV1,
    instruction_records: list[InstructionRecordV1],
    knowledge_gate: PreExecutionKnowledgeGateV1,
) -> PreL5WorkspaceBootstrapEnvelopeV1:

    active = ActiveInstructionResolverV1().resolve(
        project_id=authority_package.project_id,
        task_id=authority_package.task_id,
        state_package_id=authority_package.state_package_id,
        authority_reference=authority_package.authority_reference,
        records=instruction_records,
    )

    package_payload = authority_package.model_dump(
        mode="json"
    )

    active_payload = active.model_dump(mode="json")

    return PreL5WorkspaceBootstrapEnvelopeV1(
        authority_package=authority_package,
        active_instruction_set=active,
        knowledge_gate=knowledge_gate,
        authority_package_sha256=_sha256(package_payload),
        active_instruction_set_sha256=_sha256(
            active_payload
        ),
    )