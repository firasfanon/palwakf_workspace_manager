from __future__ import annotations

import base64
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from palwakf_orchestrator.authority_issuer_v1 import (
    AuthorityIssuerError,
    InMemoryAuthorityKeyStoreV1,
    RemoteIntentV1,
    SignTaskEnvelopeRequestV1,
    WindowsDpapiAuthorityKeyStoreV1,
    WorkspaceAuthorityIssuerV1,
)


def _unsigned_envelope() -> dict[str, object]:
    now = datetime.now(UTC)
    task_id = "C7R-PHASE-A-TEST-001"
    base = "1" * 40
    branch = "task/AGENTIC-C7R-EXECUTOR-ID-FUTUER-IT-V1"
    return {
        "contract_version": "1.0",
        "task_id": task_id,
        "project_id": "PALWAKF_AGENTIC_AI_SYSTEM",
        "project_aliases": [],
        "repository_id": "firasfanon/palwakf_agenticAi_system",
        "executor_id": "Futuer-IT",
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
            "direct_main_mutation",
            "force_push",
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
        allowed_executor_ids=("Futuer-IT",),
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
    canonical = WorkspaceAuthorityIssuerV1._canonical_bytes(payload)

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


def test_power_shell_utc_timestamps_are_canonicalized_like_agentic_pydantic() -> None:
    envelope = _unsigned_envelope()
    envelope["issued_at"] = "2026-09-30T17:00:00.1234567+00:00"
    envelope["expires_at"] = "2099-09-30T17:20:00.0000000+00:00"
    lease = envelope["execution_lease"]
    assert isinstance(lease, dict)
    lease["issued_at"] = "2026-09-30T17:00:00.7654321+00:00"
    lease["expires_at"] = "2099-09-30T17:30:00.0000000+00:00"

    canonical = WorkspaceAuthorityIssuerV1._canonical_bytes(envelope)
    payload = json.loads(canonical)

    assert payload["issued_at"] == "2026-09-30T17:00:00.123456Z"
    assert payload["expires_at"] == "2099-09-30T17:20:00Z"
    assert payload["execution_lease"]["issued_at"] == "2026-09-30T17:00:00.765432Z"
    assert payload["execution_lease"]["expires_at"] == "2099-09-30T17:30:00Z"



def test_authority_cli_is_bom_safe_for_powershell_utf8_envelopes() -> None:
    cli_source = (
        Path(__file__).parents[1] / "scripts" / "c7r_authority_cli.py"
    ).read_text(encoding="utf-8")
    assert 'args.input.read_text(encoding="utf-8-sig")' in cli_source

def test_cross_repo_c7r_signature_vector_is_stable() -> None:
    envelope = json.loads("{\"contract_version\":\"1.0\",\"task_id\":\"C7R-CROSS-CONTRACT-VECTOR-001\",\"project_id\":\"PALWAKF_AGENTIC_AI_SYSTEM\",\"project_aliases\":[],\"repository_id\":\"firasfanon/palwakf_agenticAi_system\",\"executor_id\":\"Futuer-IT\",\"task_type\":\"C7R_PHASE_A\",\"mutation_class\":\"SERVICE_MUTATION\",\"requested_capability_id\":\"c7r.phase_a\",\"arguments\":{\"operation\":\"preflight\"},\"authority_ref\":\"workspace://c7r/pre-gate-a-vector\",\"execution_lease\":{\"lease_id\":\"lease-C7R-CROSS-CONTRACT-VECTOR-001\",\"task_id\":\"C7R-CROSS-CONTRACT-VECTOR-001\",\"project_id\":\"PALWAKF_AGENTIC_AI_SYSTEM\",\"issuer_ref\":\"workspace://c7r/pre-gate-a-vector\",\"approval_class\":\"PRE_GATE_A_BOOTSTRAP\",\"allowed_capability_ids\":[\"c7r.phase_a\"],\"allowed_mutation_classes\":[\"SERVICE_MUTATION\"],\"scope_paths\":[\"C:\\\\ProgramData\\\\PalWakf\\\\c7r_phase_a_v1\"],\"base_sha\":\"1111111111111111111111111111111111111111\",\"branch\":\"task/AGENTIC-C7R-EXECUTOR-ID-FUTUER-IT-V1\",\"issued_at\":\"2026-09-30T17:00:00.7654321+00:00\",\"expires_at\":\"2099-09-30T17:30:00.0000000+00:00\",\"revocation_state\":\"ACTIVE\"},\"expected_remote_head\":\"1111111111111111111111111111111111111111\",\"expected_base_sha\":\"1111111111111111111111111111111111111111\",\"task_branch\":\"task/AGENTIC-C7R-EXECUTOR-ID-FUTUER-IT-V1\",\"scope_paths\":[\"C:\\\\ProgramData\\\\PalWakf\\\\c7r_phase_a_v1\"],\"prohibited_actions\":[\"main_merge\",\"baseline_promotion\",\"production_mutation\",\"shared_db_mutation\",\"arbitrary_shell\"],\"idempotency_key\":\"c7r-cross-contract-vector-001\",\"nonce\":\"c7r-cross-contract-vector-nonce-001\",\"issued_at\":\"2026-09-30T17:00:00.1234567+00:00\",\"expires_at\":\"2099-09-30T17:20:00.0000000+00:00\",\"max_duration_seconds\":1800,\"evidence_requirements\":[\"authority\",\"runtime_admission\",\"zero_manual_terminal\",\"no_normal_api_key_fallback\"],\"transport_metadata\":{},\"correlation_id\":\"c7r-cross-contract-vector-001\",\"checkpoint_id\":null,\"depends_on_task_ids\":[],\"model_provider_metadata\":{}}")
    issuer = WorkspaceAuthorityIssuerV1(
        key_store=InMemoryAuthorityKeyStoreV1(bytes.fromhex("01" * 32)),
        key_id="workspace-c7r-vector-v1",
        allowed_repositories=("firasfanon/palwakf_agenticAi_system",),
        allowed_executor_ids=("Futuer-IT",),
        allowed_capability_ids=("c7r.phase_a",),
    )

    result = issuer.sign(SignTaskEnvelopeRequestV1(unsigned_envelope=envelope))

    assert result.key.public_key_b64 == "iojj3XQJ8ZX9UtstPLpdcspnCb8dlBIb83SIAbQPb1w="
    assert result.envelope_hash == (
        "4e9dbae83aad4ffe172bbd7eecac166cb2b65835dba4c77ac31fc60761a9a924"
    )
    assert result.signed_envelope["authority_proof"]["signature_b64"] == (
        "UQbmru3zCrWwnwPKK9XttAOtORK1y2Fm1BkUO7hhj7nfhlHGOV+gZA+PgRL4ISVn"
        "RmBB9Cr28ouXIK4pRbrWDw=="
    )






def _channel_envelope(
    *,
    capability: str,
    mutation_class: str,
    scope_paths: list[str],
    branch: str = "task/AGENTIC-SOVEREIGN-REMOTE-CHANNEL-V1",
) -> dict[str, object]:
    envelope = _unsigned_envelope()
    envelope["requested_capability_id"] = capability
    envelope["mutation_class"] = mutation_class
    envelope["task_branch"] = branch
    envelope["scope_paths"] = scope_paths
    envelope["prohibited_actions"] = [
        "main_merge",
        "direct_main_mutation",
        "force_push",
        "baseline_promotion",
        "production_mutation",
        "shared_db_mutation",
        "arbitrary_shell",
    ]
    lease = envelope["execution_lease"]
    assert isinstance(lease, dict)
    lease["allowed_capability_ids"] = [capability]
    lease["allowed_mutation_classes"] = [mutation_class]
    lease["scope_paths"] = scope_paths
    lease["branch"] = branch
    return envelope


def _channel_issuer() -> WorkspaceAuthorityIssuerV1:
    return WorkspaceAuthorityIssuerV1(
        key_store=InMemoryAuthorityKeyStoreV1(),
        key_id="workspace-sovereign-channel-test-v1",
        allowed_repositories=("firasfanon/palwakf_agenticAi_system",),
        allowed_executor_ids=("Futuer-IT",),
        allowed_capability_ids=(
            "git.readback",
            "git.commit",
            "workspace_drive.write_learning_candidate",
        ),
    )


def test_chatgpt_remote_intent_can_authorize_bounded_git_read() -> None:
    envelope = _channel_envelope(
        capability="git.readback",
        mutation_class="READ_ONLY",
        scope_paths=["orchestrator/src"],
    )
    result = _channel_issuer().authorize_remote_intent(
        RemoteIntentV1(client_id="chatgpt", payload=envelope)
    )
    assert result.signed_envelope["requested_capability_id"] == "git.readback"
    assert "client_id" not in result.signed_envelope


def test_mind_identity_cannot_request_git_capability() -> None:
    envelope = _channel_envelope(
        capability="git.readback",
        mutation_class="READ_ONLY",
        scope_paths=["drive://knowledge/candidates"],
    )

    with pytest.raises(
        AuthorityIssuerError,
        match="CLIENT_CAPABILITY_NOT_AUTHORIZED",
    ):
        _channel_issuer().authorize_remote_intent(
            RemoteIntentV1(client_id="mind", payload=envelope)
        )


def test_remote_intent_rejects_scope_widening() -> None:
    envelope = _channel_envelope(
        capability="git.commit",
        mutation_class="SOURCE_WRITE",
        scope_paths=["C:\\Windows\\System32"],
    )
    with pytest.raises(AuthorityIssuerError, match="SCOPE_WIDENING_DENIED"):
        _channel_issuer().authorize_remote_intent(
            RemoteIntentV1(client_id="chatgpt", payload=envelope)
        )


def test_remote_intent_rejects_direct_main_mutation() -> None:
    envelope = _channel_envelope(
        capability="git.commit",
        mutation_class="SOURCE_WRITE",
        scope_paths=["orchestrator/src"],
        branch="main",
    )
    with pytest.raises(
        AuthorityIssuerError,
        match="DIRECT_MAIN_MUTATION_DENIED",
    ):
        _channel_issuer().authorize_remote_intent(
            RemoteIntentV1(client_id="chatgpt", payload=envelope)
        )


def test_remote_intent_rejects_expired_lease() -> None:
    envelope = _channel_envelope(
        capability="git.readback",
        mutation_class="READ_ONLY",
        scope_paths=["orchestrator/src"],
    )
    lease = envelope["execution_lease"]
    assert isinstance(lease, dict)
    lease["expires_at"] = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    with pytest.raises(AuthorityIssuerError, match="LEASE_EXPIRED"):
        _channel_issuer().authorize_remote_intent(
            RemoteIntentV1(client_id="chatgpt", payload=envelope)
        )


def test_remote_intent_requires_channel_prohibitions() -> None:
    envelope = _channel_envelope(
        capability="git.readback",
        mutation_class="READ_ONLY",
        scope_paths=["orchestrator/src"],
    )
    envelope["prohibited_actions"] = ["main_merge", "arbitrary_shell"]
    with pytest.raises(
        AuthorityIssuerError,
        match="CHANNEL_REQUIRED_PROHIBITED_ACTIONS_MISSING",
    ):
        _channel_issuer().authorize_remote_intent(
            RemoteIntentV1(client_id="chatgpt", payload=envelope)
        )


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI test")
def test_windows_dpapi_machine_scope_roundtrip(tmp_path: Path) -> None:
    key_path = tmp_path / "workspace-machine.dpapi"
    store = WindowsDpapiAuthorityKeyStoreV1(
        key_path,
        machine_scope=True,
    )
    first = store.load_or_create_private_key()
    second = store.load_or_create_private_key()

    assert len(first) == 32
    assert first == second
    assert key_path.is_file()
    assert key_path.read_bytes() != first
