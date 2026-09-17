from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class EvidenceKind(StrEnum):
    tests = "TESTS"
    ci = "CI"
    uat = "UAT"
    readback = "READBACK"


class EvidenceStatus(StrEnum):
    passed = "PASS"
    failed = "FAIL"


class AcceptanceEvidenceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: EvidenceKind
    status: EvidenceStatus
    reference: str = Field(min_length=3, max_length=1000)
    subject_head: str = Field(pattern=r"^[0-9a-f]{40}$")


class AcceptanceDecisionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_head: str = Field(pattern=r"^[0-9a-f]{40}$")
    required_kinds: tuple[EvidenceKind, ...]
    satisfied_kinds: tuple[EvidenceKind, ...]
    missing_kinds: tuple[EvidenceKind, ...]
    failed_kinds: tuple[EvidenceKind, ...]
    accepted: bool
    decision: Literal["ACCEPT", "REJECT"]


def evaluate_acceptance(
    *,
    subject_head: str,
    required_kinds: tuple[EvidenceKind, ...],
    evidence: tuple[AcceptanceEvidenceV1, ...],
) -> AcceptanceDecisionV1:
    normalized_head = subject_head.lower()
    relevant = [item for item in evidence if item.subject_head == normalized_head]
    by_kind: dict[EvidenceKind, list[AcceptanceEvidenceV1]] = {}
    for item in relevant:
        by_kind.setdefault(item.kind, []).append(item)

    required = tuple(dict.fromkeys(required_kinds))
    if not required:
        raise ValueError("ACCEPTANCE_REQUIREMENTS_EMPTY")
    satisfied = tuple(
        kind
        for kind in required
        if any(item.status == EvidenceStatus.passed for item in by_kind.get(kind, []))
    )
    failed = tuple(
        kind
        for kind in required
        if any(item.status == EvidenceStatus.failed for item in by_kind.get(kind, []))
    )
    missing = tuple(kind for kind in required if kind not in by_kind)
    accepted = not missing and not failed and len(satisfied) == len(required)
    return AcceptanceDecisionV1(
        subject_head=normalized_head,
        required_kinds=required,
        satisfied_kinds=satisfied,
        missing_kinds=missing,
        failed_kinds=failed,
        accepted=accepted,
        decision="ACCEPT" if accepted else "REJECT",
    )
