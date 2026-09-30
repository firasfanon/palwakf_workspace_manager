from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from palwakf_orchestrator.authority_issuer_v1 import (
    AuthorityIssuerError,
    InMemoryAuthorityKeyStoreV1,
    SignTaskEnvelopeRequestV1,
    WorkspaceAuthorityIssuerV1,
)


def _unsigned_envelope() -> dict[str, object]:
    now = datetime.now(UTC)
    task_id = "C7R-PHASE-A-TEST-001"
    base = "1" * 40
    branch = "task/AGENTIC-C7R-PRE-GATE-A-PHASE-A-CAPABILITY-V1"
    return {
        "contract_version": "1.0",
        "task_id": task_id,
        "project_id": "PALWAKF_AGENTIC_AI_SYSTEM",
        "project_aliases": [],
        "repository_id": "firasfanon/palwakf_agenticAi_system",
        "executor_id": "DESKTOP-S5A0JSB",
        "task_type": "C7R_PHASE_A",
        "mutation_class": "SERVICE_MUTATION",
        "requested_capability_id": "c7r.phase_a",
        "arguments": {"operation": "preflight"},
        "authority_ref": "workspace://c7r/pre-gate-a",
        "execution_lease": {
            "lease_id": "lease-c7r-phase-a-test-001",
            "task_id": task_id,
            "project_id": "PALWAKF_AGENTIC_AI_SYSTEM",
            "issuer_ref": "workspace://c7r/pre-gate-a",
            "approval_class": "PRE_GATE_A_BOOTSTRAP",
            "allowed_capability_ids": ["c7r.phase_a"],
            "allowed_mutation_classes": ["SERVICE_MUTATION"],
            "scope_paths": ["C:\\ProgramData\\PalWakf\\c7r_phase_a_v1"],
            "base_sha": base,
            "branch": branch,
            "issued_at": now.isoformat(),
            "expires_at": (now + timedelta(minutes=30)).isoformat(),
            "revocation_state": "ACTIVE",
        },
        "expected_remote_head": base,
        "expected_base_sha": base,
        "task_branch": branch,
        "scope_paths": ["C:\\ProgramData\\PalWakf\\c7r_phase_a_v1"],
        "prohibited_actions": [
            "main_merge",
            "baseline_promotion",
            "production_mutation",
            "shared_db_mutation",
            "arbitrary_shell",
        ],
        "idempotency_key": "c7r-phase-a-test-001",
        "nonce": "c7r-phase-a-test-nonce-001",
        "issued_at": now.isoformat(),
        "expires_at": (now + timedelta(minutes=20)).isoformat(),
        "max_duration_seconds": 900,
        "evidence_requirements": ["authority", "phase_a"],
        "transport_metadata": {},
        "correlation_id": "c7r-phase-a-test-001",
        "checkpoint_id": None,
        "depends_on_task_ids": [],
        "model_provider_metadata": {},
    }


def _issuer() -> WorkspaceAuthorityIssuerV1:
    return WorkspaceAuthorityIssuerV1(
        key_store=InMemoryAuthorityKeyStoreV1(),
        key_id="workspace-c7r-test-v1",
        allowed_repositories=("firasfanon/palwakf_agenticAi_system",),
        allowed_executor_ids=("DESKTOP-S5A0JSB",),
        allowed_capability_ids=("c7r.phase_a",),
    )


def test_signs_agentic_compatible_canonical_payload() -> None:
    issuer = _issuer()
    result = issuer.sign(SignTaskEnvelopeRequestV1(unsigned_envelope=_unsigned_envelope()))

    proof = result.signed_envelope["authority_proof"]
    descriptor = result.key
    public = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(descriptor.public_key_b64, validate=True)
    )

    payload = dict(result.signed_envelope)
    payload.pop("authority_proof")
    payload.pop("transport_metadata")
    payload.pop("model_provider_metadata")
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    public.verify(
        base64.b64decode(str(proof["signature_b64"]), validate=True),
        canonical,
    )
    assert descriptor.private_key_exportable is False
    serialized = result.model_dump(mode="json")
    assert "private_key_b64" not in serialized["key"]
    assert "private_key" not in serialized["key"]
    assert "raw_private_key" not in serialized["key"]
    assert set(serialized["key"]) == {
        "schema_id",
        "key_id",
        "algorithm",
        "public_key_b64",
        "public_key_sha256",
        "private_key_exportable",
        "owner",
    }


def test_rejects_capability_outside_pre_gate_scope() -> None:
    envelope = _unsigned_envelope()
    envelope["requested_capability_id"] = "git.commit"

    with pytest.raises(AuthorityIssuerError, match="CAPABILITY_NOT_AUTHORIZED"):
        _issuer().sign(SignTaskEnvelopeRequestV1(unsigned_envelope=envelope))


def test_rejects_head_base_drift() -> None:
    envelope = _unsigned_envelope()
    envelope["expected_remote_head"] = "2" * 40

    with pytest.raises(AuthorityIssuerError, match="EXPECTED_HEAD_BASE_MISMATCH"):
        _issuer().sign(SignTaskEnvelopeRequestV1(unsigned_envelope=envelope))


def test_rejects_missing_sovereign_prohibitions() -> None:
    envelope = _unsigned_envelope()
    envelope["prohibited_actions"] = ["arbitrary_shell"]

    with pytest.raises(
        AuthorityIssuerError,
        match="REQUIRED_PROHIBITED_ACTIONS_MISSING",
    ):
        _issuer().sign(SignTaskEnvelopeRequestV1(unsigned_envelope=envelope))
