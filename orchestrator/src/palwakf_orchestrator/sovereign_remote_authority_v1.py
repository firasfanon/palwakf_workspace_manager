from __future__ import annotations

import base64
import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict, Field, model_validator

from palwakf_orchestrator.authority_issuer_v1 import (
    AuthorityKeyDescriptorV1,
    AuthorityPrivateKeyStore,
    WindowsDpapiAuthorityKeyStoreV1,
    WorkspaceAuthorityIssuerV1,
)


PrincipalId = Literal["CHATGPT", "MIND", "AGENTIC"]
MutationClass = Literal["READ_ONLY", "TEMP_MUTATION", "SOURCE_WRITE", "SERVICE_MUTATION"]

REQUIRED_PROHIBITED_ACTIONS = (
    "main_merge",
    "force_push",
    "baseline_promotion",
    "production_mutation",
    "shared_db_mutation",
    "arbitrary_shell",
)

CHATGPT_CAPABILITIES: Mapping[str, MutationClass] = {
    "github.repo.read": "READ_ONLY",
    "github.branch.read": "READ_ONLY",
    "github.diff.read": "READ_ONLY",
    "github.file.read": "READ_ONLY",
    "github.branch.create": "SOURCE_WRITE",
    "github.file.write_bounded": "SOURCE_WRITE",
    "github.commit.create": "SOURCE_WRITE",
    "github.task_branch.push": "SOURCE_WRITE",
    "github.issue.read": "READ_ONLY",
    "github.issue.create": "SOURCE_WRITE",
    "github.issue.update": "SOURCE_WRITE",
    "github.issue.close": "SOURCE_WRITE",
    "github.pr.read": "READ_ONLY",
    "github.workflow.read": "READ_ONLY",
    "github.ci.read": "READ_ONLY",
    "workspace_drive.search": "READ_ONLY",
    "workspace_drive.list": "READ_ONLY",
    "workspace_drive.read": "READ_ONLY",
    "workspace_drive.document.find": "READ_ONLY",
    "workspace_drive.document.append_bounded": "SOURCE_WRITE",
    "workspace_drive.document.update_bounded": "SOURCE_WRITE",
    "workspace_drive.create_document": "SOURCE_WRITE",
    "workspace_drive.write_evidence": "SOURCE_WRITE",
    "workspace_drive.update_current_state": "SOURCE_WRITE",
    "engineering.codex.analyze": "READ_ONLY",
    "engineering.codex.plan": "READ_ONLY",
    "engineering.codex.review_diff": "READ_ONLY",
    "engineering.codex.edit_bounded": "SOURCE_WRITE",
    "engineering.codex.test": "TEMP_MUTATION",
    "engineering.codex.debug": "TEMP_MUTATION",
    "ollama.infer": "READ_ONLY",
    "playwright.uat": "TEMP_MUTATION",
    "health.check": "READ_ONLY",
}

MIND_CAPABILITIES: Mapping[str, MutationClass] = {
    "github.repo.read": "READ_ONLY",
    "github.branch.read": "READ_ONLY",
    "github.diff.read": "READ_ONLY",
    "github.file.read": "READ_ONLY",
    "workspace_drive.search": "READ_ONLY",
    "workspace_drive.list": "READ_ONLY",
    "workspace_drive.read": "READ_ONLY",
    "workspace_drive.document.find": "READ_ONLY",
    "workspace_drive.write_learning_candidate": "SOURCE_WRITE",
    "workspace_drive.write_memory_candidate": "SOURCE_WRITE",
    "workspace_drive.write_knowledge_candidate": "SOURCE_WRITE",
    "health.check": "READ_ONLY",
}

AGENTIC_CAPABILITIES: Mapping[str, MutationClass] = {
    **CHATGPT_CAPABILITIES,
    "transport.reconnect": "SERVICE_MUTATION",
    "service.restart": "SERVICE_MUTATION",
    "runtime.repair": "SERVICE_MUTATION",
    "worktree.repair": "SERVICE_MUTATION",
    "config.restore": "SERVICE_MUTATION",
    "trust.rotate": "SERVICE_MUTATION",
    "runtime.update.stage": "SERVICE_MUTATION",
    "runtime.update.activate": "SERVICE_MUTATION",
    "runtime.update.rollback": "SERVICE_MUTATION",
}


class SovereignAuthorityError(RuntimeError):
    pass


class PrincipalPolicyV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    principal_id: PrincipalId
    capability_mutation_classes: dict[str, MutationClass]
    allowed_repositories: tuple[str, ...] = ()
    service_admin_approval_class: str | None = None

    def mutation_class_for(self, capability_id: str) -> MutationClass:
        mutation = self.capability_mutation_classes.get(capability_id)
        if mutation is None:
            raise SovereignAuthorityError("CAPABILITY_NOT_AUTHORIZED_FOR_PRINCIPAL")
        return mutation


class RemoteIntentV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_id: Literal["palwakf.sovereign_remote_intent.v1"] = (
        "palwakf.sovereign_remote_intent.v1"
    )
    intent_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{8,200}$")
    principal_id: PrincipalId
    project_id: str = Field(min_length=3, max_length=200)
    repository_id: str = Field(min_length=3, max_length=240)
    executor_id: str = Field(default="Futuer-IT", min_length=3, max_length=160)
    requested_capability_id: str = Field(min_length=3, max_length=160)
    mutation_class: MutationClass
    arguments: dict[str, Any] = Field(default_factory=dict)
    task_branch: str = Field(min_length=5, max_length=240)
    expected_remote_head: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    expected_base_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    scope_paths: tuple[str, ...] = Field(default=(), max_length=128)
    evidence_requirements: tuple[str, ...] = Field(default=(), max_length=64)
    approval_class: str = Field(default="SOVEREIGN_REMOTE_EXECUTION", max_length=120)
    max_duration_seconds: int = Field(default=1800, ge=1, le=7200)
    idempotency_key: str = Field(min_length=8, max_length=240)
    nonce: str = Field(min_length=8, max_length=240)
    issued_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def validate_intent(self) -> "RemoteIntentV1":
        if self.issued_at.tzinfo is None or self.expires_at.tzinfo is None:
            raise ValueError("INTENT_TIMESTAMPS_MUST_BE_TIMEZONE_AWARE")
        if self.expires_at <= self.issued_at:
            raise ValueError("INTENT_EXPIRY_MUST_FOLLOW_ISSUE")
        if self.expected_remote_head.lower() != self.expected_base_sha.lower():
            raise ValueError("EXPECTED_REMOTE_HEAD_MUST_EQUAL_BASE_AT_AUTHORIZATION")
        if self.mutation_class != "READ_ONLY" and not self.task_branch.startswith("task/"):
            raise ValueError("MUTATION_REQUIRES_TASK_BRANCH")
        if self.mutation_class != "READ_ONLY" and not self.scope_paths:
            raise ValueError("MUTATION_SCOPE_REQUIRED")
        return self


class SovereignTaskReceiptV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_id: Literal["palwakf.sovereign_task_receipt.v1"] = (
        "palwakf.sovereign_task_receipt.v1"
    )
    intent_id: str
    task_id: str
    principal_id: PrincipalId
    executor_id: str
    capability_id: str
    repository_id: str
    task_branch: str
    envelope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    authority_key_id: str
    transport_id: str
    result_ref: str | None = None
    state: Literal["SIGNED", "PUBLISHED"]


class TaskPublisher(Protocol):
    transport_id: str

    def publish(self, *, task_id: str, envelope: Mapping[str, Any]) -> str: ...

    def result(self, task_id: str) -> Mapping[str, Any] | None: ...


class LocalSpoolTaskPublisherV1:
    transport_id = "local-spool-v1"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.inbox = root / "inbox"
        self.results = root / "results"
        self.inbox.mkdir(parents=True, exist_ok=True)
        self.results.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _safe_task_name(task_id: str) -> str:
        if not task_id or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.:-" for char in task_id):
            raise SovereignAuthorityError("TASK_ID_NOT_SPOOL_SAFE")
        return task_id

    def publish(self, *, task_id: str, envelope: Mapping[str, Any]) -> str:
        safe_id = self._safe_task_name(task_id)
        target = self.inbox / f"{safe_id}.json"
        if target.exists():
            existing = json.loads(target.read_text(encoding="utf-8"))
            if existing != dict(envelope):
                raise SovereignAuthorityError("SPOOL_TASK_ID_REUSED_WITH_DIFFERENT_ENVELOPE")
            return str(target)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(
            json.dumps(dict(envelope), ensure_ascii=False, sort_keys=True, default=str),
            encoding="utf-8",
        )
        os.replace(tmp, target)
        return str(target)

    def result(self, task_id: str) -> Mapping[str, Any] | None:
        safe_id = self._safe_task_name(task_id)
        target = self.results / f"{safe_id}.json"
        if not target.is_file():
            return None
        payload = json.loads(target.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise SovereignAuthorityError("SPOOL_RESULT_NOT_OBJECT")
        return payload


class SovereignWorkspaceAuthorityV1:
    def __init__(
        self,
        *,
        key_store: AuthorityPrivateKeyStore,
        key_id: str,
        policies: Mapping[PrincipalId, PrincipalPolicyV1],
        allowed_executor_ids: tuple[str, ...] = ("Futuer-IT",),
        client_principal_bindings: Mapping[str, PrincipalId] | None = None,
    ) -> None:
        self._key_store = key_store
        self._key_id = key_id
        self._policies = dict(policies)
        self._allowed_executor_ids = set(allowed_executor_ids)
        self._client_bindings = {
            key.casefold(): value
            for key, value in (
                client_principal_bindings
                or {
                    "chatgpt": "CHATGPT",
                    "mind": "MIND",
                    "agentic": "AGENTIC",
                }
            ).items()
        }

    def public_descriptor(self) -> AuthorityKeyDescriptorV1:
        private = Ed25519PrivateKey.from_private_bytes(
            self._key_store.load_or_create_private_key()
        )
        raw_public = private.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        return AuthorityKeyDescriptorV1(
            key_id=self._key_id,
            public_key_b64=base64.b64encode(raw_public).decode("ascii"),
            public_key_sha256=hashlib.sha256(raw_public).hexdigest(),
        )

    def resolve_authenticated_principal(self, client_id: str) -> PrincipalId:
        principal = self._client_bindings.get(client_id.casefold())
        if principal is None:
            raise SovereignAuthorityError("MCP_CLIENT_NOT_BOUND_TO_SOVEREIGN_PRINCIPAL")
        return principal

    def issue(
        self,
        intent: RemoteIntentV1,
        *,
        authenticated_client_id: str,
    ) -> tuple[dict[str, Any], str, AuthorityKeyDescriptorV1]:
        principal = self.resolve_authenticated_principal(authenticated_client_id)
        if principal != intent.principal_id:
            raise SovereignAuthorityError("AUTHENTICATED_PRINCIPAL_MISMATCH")
        if intent.executor_id not in self._allowed_executor_ids:
            raise SovereignAuthorityError("EXECUTOR_NOT_AUTHORIZED")
        policy = self._policies.get(principal)
        if policy is None:
            raise SovereignAuthorityError("PRINCIPAL_POLICY_NOT_FOUND")
        expected_mutation = policy.mutation_class_for(intent.requested_capability_id)
        if expected_mutation != intent.mutation_class:
            raise SovereignAuthorityError("CAPABILITY_MUTATION_CLASS_MISMATCH")
        if policy.allowed_repositories and intent.repository_id not in policy.allowed_repositories:
            raise SovereignAuthorityError("REPOSITORY_NOT_AUTHORIZED_FOR_PRINCIPAL")
        if (
            intent.mutation_class == "SERVICE_MUTATION"
            and policy.service_admin_approval_class is not None
            and intent.approval_class != policy.service_admin_approval_class
        ):
            raise SovereignAuthorityError("SERVICE_ADMIN_APPROVAL_CLASS_REQUIRED")

        task_id = f"SOV-{principal}-{intent.intent_id}"
        authority_ref = f"workspace://sovereign-channel/principal/{principal}"
        unsigned: dict[str, Any] = {
            "contract_version": "1.0",
            "task_id": task_id,
            "project_id": intent.project_id,
            "project_aliases": [f"principal:{principal}"],
            "repository_id": intent.repository_id,
            "executor_id": intent.executor_id,
            "task_type": f"SOVEREIGN_REMOTE_{principal}",
            "mutation_class": intent.mutation_class,
            "requested_capability_id": intent.requested_capability_id,
            "arguments": intent.arguments,
            "authority_ref": authority_ref,
            "execution_lease": {
                "lease_id": f"lease-{intent.intent_id}",
                "task_id": task_id,
                "project_id": intent.project_id,
                "issuer_ref": authority_ref,
                "approval_class": intent.approval_class,
                "allowed_capability_ids": [intent.requested_capability_id],
                "allowed_mutation_classes": [intent.mutation_class],
                "scope_paths": list(intent.scope_paths),
                "base_sha": intent.expected_base_sha,
                "branch": intent.task_branch,
                "issued_at": intent.issued_at.isoformat(),
                "expires_at": intent.expires_at.isoformat(),
                "revocation_state": "ACTIVE",
            },
            "expected_remote_head": intent.expected_remote_head,
            "expected_base_sha": intent.expected_base_sha,
            "task_branch": intent.task_branch,
            "scope_paths": list(intent.scope_paths),
            "prohibited_actions": list(REQUIRED_PROHIBITED_ACTIONS),
            "idempotency_key": intent.idempotency_key,
            "nonce": intent.nonce,
            "issued_at": intent.issued_at.isoformat(),
            "expires_at": intent.expires_at.isoformat(),
            "max_duration_seconds": intent.max_duration_seconds,
            "evidence_requirements": list(intent.evidence_requirements),
            "transport_metadata": {},
            "correlation_id": intent.intent_id,
            "checkpoint_id": None,
            "depends_on_task_ids": [],
            "model_provider_metadata": {},
        }
        canonical = WorkspaceAuthorityIssuerV1._canonical_bytes(unsigned)
        private = Ed25519PrivateKey.from_private_bytes(
            self._key_store.load_or_create_private_key()
        )
        signature = private.sign(canonical)
        signed = dict(unsigned)
        signed["authority_proof"] = {
            "algorithm": "ED25519",
            "key_id": self._key_id,
            "signature_b64": base64.b64encode(signature).decode("ascii"),
        }
        return signed, hashlib.sha256(canonical).hexdigest(), self.public_descriptor()


class SovereignRemoteChannelServiceV1:
    def __init__(
        self,
        authority: SovereignWorkspaceAuthorityV1,
        publisher: TaskPublisher,
    ) -> None:
        self.authority = authority
        self.publisher = publisher

    def submit(
        self,
        intent: RemoteIntentV1,
        *,
        authenticated_client_id: str,
    ) -> SovereignTaskReceiptV1:
        signed, envelope_hash, descriptor = self.authority.issue(
            intent,
            authenticated_client_id=authenticated_client_id,
        )
        task_id = str(signed["task_id"])
        result_ref = self.publisher.publish(task_id=task_id, envelope=signed)
        return SovereignTaskReceiptV1(
            intent_id=intent.intent_id,
            task_id=task_id,
            principal_id=intent.principal_id,
            executor_id=intent.executor_id,
            capability_id=intent.requested_capability_id,
            repository_id=intent.repository_id,
            task_branch=intent.task_branch,
            envelope_hash=envelope_hash,
            authority_key_id=descriptor.key_id,
            transport_id=self.publisher.transport_id,
            result_ref=result_ref,
            state="PUBLISHED",
        )

    def result(self, task_id: str) -> Mapping[str, Any] | None:
        return self.publisher.result(task_id)


def default_principal_policies() -> dict[PrincipalId, PrincipalPolicyV1]:
    repositories = (
        "firasfanon/palwakf_workspace_manager",
        "firasfanon/palwakf_mind_assistant",
        "firasfanon/palwakf_agenticAi_system",
    )
    return {
        "CHATGPT": PrincipalPolicyV1(
            principal_id="CHATGPT",
            capability_mutation_classes=dict(CHATGPT_CAPABILITIES),
            allowed_repositories=repositories,
        ),
        "MIND": PrincipalPolicyV1(
            principal_id="MIND",
            capability_mutation_classes=dict(MIND_CAPABILITIES),
            allowed_repositories=repositories,
        ),
        "AGENTIC": PrincipalPolicyV1(
            principal_id="AGENTIC",
            capability_mutation_classes=dict(AGENTIC_CAPABILITIES),
            allowed_repositories=repositories,
            service_admin_approval_class="SOVEREIGN_SELF_RECOVERY",
        ),
    }


def build_default_sovereign_channel_service() -> SovereignRemoteChannelServiceV1:
    key_path = Path(
        os.environ.get(
            "PALWAKF_SOVEREIGN_AUTHORITY_KEY_PATH",
            r"C:\ProgramData\PalWakf\workspace_authority_v1\secrets\workspace-ed25519.dpapi",
        )
    )
    bindings_raw = os.environ.get("PALWAKF_SOVEREIGN_PRINCIPAL_BINDINGS_JSON")
    bindings: Mapping[str, PrincipalId] | None = None
    if bindings_raw:
        parsed = json.loads(bindings_raw)
        if not isinstance(parsed, dict):
            raise SovereignAuthorityError("PRINCIPAL_BINDINGS_MUST_BE_OBJECT")
        normalized: dict[str, PrincipalId] = {}
        for key, value in parsed.items():
            if value not in {"CHATGPT", "MIND", "AGENTIC"}:
                raise SovereignAuthorityError("PRINCIPAL_BINDING_VALUE_INVALID")
            normalized[str(key)] = value
        bindings = normalized

    authority = SovereignWorkspaceAuthorityV1(
        key_store=WindowsDpapiAuthorityKeyStoreV1(key_path),
        key_id=os.environ.get(
            "PALWAKF_SOVEREIGN_AUTHORITY_KEY_ID",
            "workspace-sovereign-channel-v1",
        ),
        policies=default_principal_policies(),
        client_principal_bindings=bindings,
    )
    spool_root = Path(
        os.environ.get(
            "PALWAKF_SOVEREIGN_SPOOL_ROOT",
            r"C:\ProgramData\PalWakf\sovereign_channel_v1",
        )
    )
    return SovereignRemoteChannelServiceV1(
        authority,
        LocalSpoolTaskPublisherV1(spool_root),
    )
