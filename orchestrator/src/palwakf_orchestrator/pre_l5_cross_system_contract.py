from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.intersystem_contracts import (
    WorkspaceAuthorityPackageV1,
)
from palwakf_orchestrator.pre_l5_instruction_resolver import (
    PreL5WorkspaceBootstrapEnvelopeV1,
)


class PreL5InstructionProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction_id: str
    authority: str
    version: str
    effective_at: str
    applies_to_projects: tuple[str, ...]
    supersedes: tuple[str, ...] = ()


class PreL5InstructionExclusionProjectionV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction_id: str
    reason: str


class PreL5FailureFingerprintBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fingerprint_id: str
    lesson_id: str
    preventive_gate_id: str
    relevant: bool = True
    applies_to_projects: tuple[str, ...] = ("*",)


class PreL5CrossSystemContractV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal[
        "PALWAKF_PRE_L5_CROSS_SYSTEM_CONTRACT_V1"
    ] = "PALWAKF_PRE_L5_CROSS_SYSTEM_CONTRACT_V1"

    project_id: str
    task_id: str
    state_package_id: str
    execution_run_id: str
    authority_reference: str

    authority_package: WorkspaceAuthorityPackageV1

    active_instruction_set_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )

    active_instructions: tuple[
        PreL5InstructionProjectionV1, ...
    ]

    instruction_exclusions: tuple[
        PreL5InstructionExclusionProjectionV1, ...
    ] = ()

    active_lesson_ids: tuple[str, ...]
    reused_lesson_ids: tuple[str, ...]

    known_failure_fingerprints: tuple[
        PreL5FailureFingerprintBindingV1, ...
    ] = ()

    applicable_skill_ids: tuple[str, ...] = ()
    preventive_gate_ids: tuple[str, ...] = ()

    execution_admission: Literal["READY"] = "READY"
    canonical_promotion_allowed: Literal[False] = False

    @model_validator(mode="after")
    def validate_binding(self):
        package = self.authority_package

        if package.project_id != self.project_id:
            raise ValueError(
                "CROSS_SYSTEM_PROJECT_BINDING_MISMATCH"
            )

        if package.task_id != self.task_id:
            raise ValueError(
                "CROSS_SYSTEM_TASK_BINDING_MISMATCH"
            )

        if package.state_package_id != self.state_package_id:
            raise ValueError(
                "CROSS_SYSTEM_STATE_PACKAGE_BINDING_MISMATCH"
            )

        if package.execution_run_id != self.execution_run_id:
            raise ValueError(
                "CROSS_SYSTEM_EXECUTION_RUN_BINDING_MISMATCH"
            )

        if package.authority_reference != self.authority_reference:
            raise ValueError(
                "CROSS_SYSTEM_AUTHORITY_BINDING_MISMATCH"
            )

        if not self.active_instructions:
            raise ValueError(
                "CROSS_SYSTEM_ACTIVE_INSTRUCTION_SET_EMPTY"
            )

        active_ids = {
            item.instruction_id
            for item in self.active_instructions
        }

        if len(active_ids) != len(self.active_instructions):
            raise ValueError(
                "CROSS_SYSTEM_DUPLICATE_ACTIVE_INSTRUCTION"
            )

        excluded_ids = {
            item.instruction_id
            for item in self.instruction_exclusions
        }

        if active_ids.intersection(excluded_ids):
            raise ValueError(
                "CROSS_SYSTEM_EXCLUDED_INSTRUCTION_REENTERED"
            )

        active_lessons = set(self.active_lesson_ids)
        reused_lessons = set(self.reused_lesson_ids)
        preventive_gates = set(self.preventive_gate_ids)

        if not reused_lessons.issubset(active_lessons):
            raise ValueError(
                "CROSS_SYSTEM_REUSED_LESSON_NOT_ACTIVE"
            )

        for fingerprint in self.known_failure_fingerprints:
            if not fingerprint.relevant:
                continue

            projects = set(
                fingerprint.applies_to_projects
            )

            if (
                "*" not in projects
                and self.project_id not in projects
            ):
                raise ValueError(
                    "CROSS_SYSTEM_FAILURE_FINGERPRINT_PROJECT_LEAKAGE"
                )

            if fingerprint.lesson_id not in active_lessons:
                raise ValueError(
                    "CROSS_SYSTEM_KNOWN_LESSON_NOT_ACTIVE"
                )

            if fingerprint.lesson_id not in reused_lessons:
                raise ValueError(
                    "CROSS_SYSTEM_KNOWN_LESSON_NOT_REUSED"
                )

            if (
                fingerprint.preventive_gate_id
                not in preventive_gates
            ):
                raise ValueError(
                    "CROSS_SYSTEM_PREVENTIVE_GATE_NOT_ACTIVE"
                )

        return self


def build_pre_l5_cross_system_contract(
    *,
    bootstrap: PreL5WorkspaceBootstrapEnvelopeV1,
    reused_lesson_ids: tuple[str, ...],
    failure_fingerprints: tuple[
        PreL5FailureFingerprintBindingV1, ...
    ],
) -> PreL5CrossSystemContractV1:

    if bootstrap.execution_admission != "READY":
        raise ValueError(
            "WORKSPACE_PRE_L5_EXECUTION_NOT_ADMITTED"
        )

    active = bootstrap.active_instruction_set
    knowledge = bootstrap.knowledge_gate
    package = bootstrap.authority_package

    expected_fingerprints = set(
        knowledge.known_failure_fingerprint_ids
    )

    provided_fingerprints = {
        item.fingerprint_id
        for item in failure_fingerprints
    }

    if expected_fingerprints != provided_fingerprints:
        raise ValueError(
            "WORKSPACE_FAILURE_FINGERPRINT_BINDING_INCOMPLETE"
        )

    return PreL5CrossSystemContractV1(
        project_id=package.project_id,
        task_id=package.task_id,
        state_package_id=package.state_package_id,
        execution_run_id=package.execution_run_id,
        authority_reference=package.authority_reference,
        authority_package=package,
        active_instruction_set_sha256=(
            bootstrap.active_instruction_set_sha256
        ),
        active_instructions=tuple(
            PreL5InstructionProjectionV1(
                instruction_id=item.instruction_id,
                authority=item.authority,
                version=item.version,
                effective_at=item.effective_at.isoformat(),
                applies_to_projects=item.applies_to_projects,
                supersedes=item.supersedes,
            )
            for item in active.active_instructions
        ),
        instruction_exclusions=tuple(
            PreL5InstructionExclusionProjectionV1(
                instruction_id=item.instruction_id,
                reason=item.reason,
            )
            for item in active.exclusions
        ),
        active_lesson_ids=knowledge.active_lesson_ids,
        reused_lesson_ids=reused_lesson_ids,
        known_failure_fingerprints=failure_fingerprints,
        applicable_skill_ids=knowledge.applicable_skill_ids,
        preventive_gate_ids=knowledge.preventive_gate_ids,
    )
