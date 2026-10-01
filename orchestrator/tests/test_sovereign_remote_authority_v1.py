from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from palwakf_orchestrator.authority_issuer_v1 import InMemoryAuthorityKeyStoreV1
from palwakf_orchestrator.sovereign_remote_authority_v1 import (
    LocalSpoolTaskPublisherV1,
    RemoteIntentV1,
    SovereignAuthorityError,
    SovereignRemoteChannelServiceV1,
    SovereignWorkspaceAuthorityV1,
    default_principal_policies,
)


BASE = "1" * 40


def _authority() -> SovereignWorkspaceAuthorityV1:
    return SovereignWorkspaceAuthorityV1(
        key_store=InMemoryAuthorityKeyStoreV1(bytes.fromhex("02" * 32)),
        key_id="workspace-sovereign-test-v1",
        policies=default_principal_policies(),
        client_principal_bindings={
            "chat-client": "CHATGPT",
            "mind-client": "MIND",
            "agentic-client": "AGENTIC",
        },
    )


def _intent(
    *,
    principal: str = "CHATGPT",
    capability: str = "github.repo.read",
    mutation_class: str = "READ_ONLY",
    approval_class: str = "SOVEREIGN_REMOTE_EXECUTION",
    scope_paths: tuple[str, ...] = (),
) -> RemoteIntentV1:
    now = datetime.now(UTC)
    return RemoteIntentV1(
        intent_id=f"intent-{principal.lower()}-001",
        principal_id=principal,
        project_id="PALWAKF_AGENTIC_AI_SYSTEM",
        repository_id="firasfanon/palwakf_agenticAi_system",
        requested_capability_id=capability,
        mutation_class=mutation_class,
        arguments={"repo_root": r"C:\repo"},
        task_branch="task/SOVEREIGN-TEST-V1",
        expected_remote_head=BASE,
        expected_base_sha=BASE,
        scope_paths=scope_paths,
        evidence_requirements=("authority", "principal", "drift"),
        approval_class=approval_class,
        idempotency_key=f"idempotency-{principal.lower()}-001",
        nonce=f"nonce-{principal.lower()}-001",
        issued_at=now,
        expires_at=now + timedelta(minutes=30),
    )


def test_chatgpt_intent_is_signed_and_principal_is_in_signed_payload() -> None:
    authority = _authority()
    intent = _intent()

    signed, envelope_hash, descriptor = authority.issue(
        intent,
        authenticated_client_id="chat-client",
    )

    assert len(envelope_hash) == 64
    assert signed["executor_id"] == "Futuer-IT"
    assert signed["task_type"] == "SOVEREIGN_REMOTE_CHATGPT"
    assert signed["authority_ref"].endswith("/CHATGPT")
    assert signed["project_aliases"] == ["principal:CHATGPT"]
    assert signed["requested_capability_id"] == "github.repo.read"
    assert "force_push" in signed["prohibited_actions"]

    proof = signed["authority_proof"]
    public = Ed25519PublicKey.from_public_bytes(
        base64.b64decode(descriptor.public_key_b64, validate=True)
    )
    canonical = dict(signed)
    canonical.pop("authority_proof")
    from palwakf_orchestrator.authority_issuer_v1 import WorkspaceAuthorityIssuerV1

    public.verify(
        base64.b64decode(proof["signature_b64"], validate=True),
        WorkspaceAuthorityIssuerV1._canonical_bytes(canonical),
    )


def test_authenticated_principal_cannot_impersonate_another_principal() -> None:
    with pytest.raises(
        SovereignAuthorityError,
        match="AUTHENTICATED_PRINCIPAL_MISMATCH",
    ):
        _authority().issue(
            _intent(principal="MIND"),
            authenticated_client_id="chat-client",
        )


def test_mind_cannot_request_source_code_mutation() -> None:
    intent = _intent(
        principal="MIND",
        capability="github.file.write_bounded",
        mutation_class="SOURCE_WRITE",
        scope_paths=("docs/",),
    )
    with pytest.raises(
        SovereignAuthorityError,
        match="CAPABILITY_NOT_AUTHORIZED_FOR_PRINCIPAL",
    ):
        _authority().issue(intent, authenticated_client_id="mind-client")


def test_agentic_service_admin_requires_dedicated_approval_class() -> None:
    intent = _intent(
        principal="AGENTIC",
        capability="runtime.repair",
        mutation_class="SERVICE_MUTATION",
        approval_class="SOVEREIGN_REMOTE_EXECUTION",
        scope_paths=(r"C:\ProgramData\PalWakf",),
    )
    with pytest.raises(
        SovereignAuthorityError,
        match="SERVICE_ADMIN_APPROVAL_CLASS_REQUIRED",
    ):
        _authority().issue(intent, authenticated_client_id="agentic-client")


def test_spool_publisher_is_atomic_idempotent_and_persistent(tmp_path) -> None:
    publisher = LocalSpoolTaskPublisherV1(tmp_path)
    service = SovereignRemoteChannelServiceV1(_authority(), publisher)
    intent = _intent()

    receipt = service.submit(intent, authenticated_client_id="chat-client")

    assert receipt.state == "PUBLISHED"
    assert receipt.transport_id == "local-spool-v1"
    path = tmp_path / "inbox" / f"{receipt.task_id}.json"
    assert path.is_file()
    envelope = json.loads(path.read_text(encoding="utf-8"))
    assert envelope["task_id"] == receipt.task_id
    assert envelope["authority_ref"].endswith("/CHATGPT")

    second = service.submit(intent, authenticated_client_id="chat-client")
    assert second.envelope_hash == receipt.envelope_hash
    assert second.result_ref == receipt.result_ref


def test_spool_result_readback_is_bounded_to_task_id(tmp_path) -> None:
    publisher = LocalSpoolTaskPublisherV1(tmp_path)
    task_id = "SOV-CHATGPT-intent-chatgpt-001"
    result_path = tmp_path / "results" / f"{task_id}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps({"task_id": task_id, "exit_state": "COMPLETED"}),
        encoding="utf-8",
    )

    result = publisher.result(task_id)

    assert result == {"task_id": task_id, "exit_state": "COMPLETED"}
