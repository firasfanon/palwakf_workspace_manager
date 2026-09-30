from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel, ConfigDict, Field


class AuthorityIssuerError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class AuthorityKeyDescriptorV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_id: str = "palwakf.workspace_authority_key.v1"
    key_id: str
    algorithm: str = "ED25519"
    public_key_b64: str
    public_key_sha256: str
    private_key_exportable: bool = False
    owner: str = "PALWAKF_WORKSPACE_MANAGER"


class SignTaskEnvelopeRequestV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    unsigned_envelope: dict[str, Any]


class SignedTaskEnvelopeResponseV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    key: AuthorityKeyDescriptorV1
    envelope_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    signed_envelope: dict[str, Any]


class AuthorityPrivateKeyStore(Protocol):
    def load_or_create_private_key(self) -> bytes: ...


@dataclass
class InMemoryAuthorityKeyStoreV1:
    raw_private_key: bytes | None = None

    def load_or_create_private_key(self) -> bytes:
        if self.raw_private_key is None:
            self.raw_private_key = Ed25519PrivateKey.generate().private_bytes(
                serialization.Encoding.Raw,
                serialization.PrivateFormat.Raw,
                serialization.NoEncryption(),
            )
        return self.raw_private_key


class WindowsDpapiAuthorityKeyStoreV1:
    """Persist one Ed25519 private key encrypted with Windows DPAPI."""

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def __init__(self, path: Path) -> None:
        self.path = path

    def load_or_create_private_key(self) -> bytes:
        if self.path.exists():
            raw = self._unprotect(self.path.read_bytes())
            if len(raw) != 32:
                raise AuthorityIssuerError("AUTHORITY_PRIVATE_KEY_LENGTH_INVALID")
            return raw

        raw = Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        protected = self._protect(raw)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_bytes(protected)
        os.replace(tmp, self.path)
        return raw

    @staticmethod
    def _make_blob(data: bytes) -> tuple[_DataBlob, Any]:
        buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
        blob = _DataBlob(
            len(data),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
        )
        return blob, buffer

    @classmethod
    def _protect(cls, plain: bytes) -> bytes:
        if os.name != "nt":
            raise AuthorityIssuerError("WINDOWS_DPAPI_REQUIRES_WINDOWS")
        in_blob, keepalive = cls._make_blob(plain)
        out_blob = _DataBlob()
        _ = keepalive
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            raise AuthorityIssuerError("WINDOWS_DPAPI_LIBRARY_UNAVAILABLE")
        crypt32 = windll.crypt32
        kernel32 = windll.kernel32
        ok = crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            "PalWakf Workspace Authority Issuer",
            None,
            None,
            None,
            cls._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise AuthorityIssuerError("WINDOWS_DPAPI_PROTECT_FAILED")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)

    @classmethod
    def _unprotect(cls, protected: bytes) -> bytes:
        if os.name != "nt":
            raise AuthorityIssuerError("WINDOWS_DPAPI_REQUIRES_WINDOWS")
        in_blob, keepalive = cls._make_blob(protected)
        out_blob = _DataBlob()
        _ = keepalive
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            raise AuthorityIssuerError("WINDOWS_DPAPI_LIBRARY_UNAVAILABLE")
        crypt32 = windll.crypt32
        kernel32 = windll.kernel32
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            None,
            None,
            None,
            cls._CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise AuthorityIssuerError("WINDOWS_DPAPI_UNPROTECT_FAILED")
        try:
            return ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            kernel32.LocalFree(out_blob.pbData)


class WorkspaceAuthorityIssuerV1:
    def __init__(
        self,
        *,
        key_store: AuthorityPrivateKeyStore,
        key_id: str,
        allowed_repositories: tuple[str, ...],
        allowed_executor_ids: tuple[str, ...],
        allowed_capability_ids: tuple[str, ...],
    ) -> None:
        self._key_store = key_store
        self._key_id = key_id
        self._allowed_repositories = set(allowed_repositories)
        self._allowed_executor_ids = set(allowed_executor_ids)
        self._allowed_capability_ids = set(allowed_capability_ids)

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

    def sign(self, request: SignTaskEnvelopeRequestV1) -> SignedTaskEnvelopeResponseV1:
        envelope = deepcopy(request.unsigned_envelope)
        self._validate_envelope(envelope)
        canonical = self._canonical_bytes(envelope)
        private = Ed25519PrivateKey.from_private_bytes(
            self._key_store.load_or_create_private_key()
        )
        signature = private.sign(canonical)
        envelope["authority_proof"] = {
            "algorithm": "ED25519",
            "key_id": self._key_id,
            "signature_b64": base64.b64encode(signature).decode("ascii"),
        }
        return SignedTaskEnvelopeResponseV1(
            key=self.public_descriptor(),
            envelope_hash=hashlib.sha256(canonical).hexdigest(),
            signed_envelope=envelope,
        )

    def _validate_envelope(self, envelope: Mapping[str, Any]) -> None:
        if "authority_proof" in envelope:
            raise AuthorityIssuerError("AUTHORITY_PROOF_MUST_BE_ABSENT_BEFORE_SIGNING")
        repository = str(envelope.get("repository_id") or "")
        executor_id = str(envelope.get("executor_id") or "")
        capability = str(envelope.get("requested_capability_id") or "")
        mutation_class = str(envelope.get("mutation_class") or "")
        branch = str(envelope.get("task_branch") or "")
        expected_remote_head = str(envelope.get("expected_remote_head") or "").lower()
        expected_base_sha = str(envelope.get("expected_base_sha") or "").lower()
        lease = envelope.get("execution_lease")

        if repository not in self._allowed_repositories:
            raise AuthorityIssuerError("REPOSITORY_NOT_AUTHORIZED")
        if executor_id not in self._allowed_executor_ids:
            raise AuthorityIssuerError("EXECUTOR_NOT_AUTHORIZED")
        if capability not in self._allowed_capability_ids:
            raise AuthorityIssuerError("CAPABILITY_NOT_AUTHORIZED")
        if mutation_class != "SERVICE_MUTATION":
            raise AuthorityIssuerError("PRE_GATE_A_REQUIRES_SERVICE_MUTATION")
        if not branch.startswith("task/"):
            raise AuthorityIssuerError("TASK_BRANCH_REQUIRED")
        if len(expected_remote_head) != 40 or expected_remote_head != expected_base_sha:
            raise AuthorityIssuerError("EXPECTED_HEAD_BASE_MISMATCH")
        if not isinstance(lease, Mapping):
            raise AuthorityIssuerError("EXECUTION_LEASE_REQUIRED")
        if str(lease.get("task_id") or "") != str(envelope.get("task_id") or ""):
            raise AuthorityIssuerError("LEASE_TASK_MISMATCH")
        if str(lease.get("project_id") or "") != str(envelope.get("project_id") or ""):
            raise AuthorityIssuerError("LEASE_PROJECT_MISMATCH")
        if str(lease.get("branch") or "") != branch:
            raise AuthorityIssuerError("LEASE_BRANCH_MISMATCH")
        if str(lease.get("base_sha") or "").lower() != expected_base_sha:
            raise AuthorityIssuerError("LEASE_BASE_MISMATCH")
        if capability not in tuple(lease.get("allowed_capability_ids") or ()):
            raise AuthorityIssuerError("LEASE_CAPABILITY_NOT_ALLOWED")
        if mutation_class not in tuple(lease.get("allowed_mutation_classes") or ()):
            raise AuthorityIssuerError("LEASE_MUTATION_CLASS_NOT_ALLOWED")
        prohibited = set(envelope.get("prohibited_actions") or ())
        required_prohibited = {
            "main_merge",
            "baseline_promotion",
            "production_mutation",
            "shared_db_mutation",
            "arbitrary_shell",
        }
        if not required_prohibited.issubset(prohibited):
            raise AuthorityIssuerError("REQUIRED_PROHIBITED_ACTIONS_MISSING")
        self._require_future_expiry(envelope.get("expires_at"), "TASK")
        self._require_future_expiry(lease.get("expires_at"), "LEASE")

    @staticmethod
    def _require_future_expiry(value: Any, prefix: str) -> None:
        if not isinstance(value, str):
            raise AuthorityIssuerError(f"{prefix}_EXPIRY_REQUIRED")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AuthorityIssuerError(f"{prefix}_EXPIRY_INVALID") from exc
        if parsed.tzinfo is None or parsed <= datetime.now(UTC):
            raise AuthorityIssuerError(f"{prefix}_EXPIRED")

    @staticmethod
    def _canonical_datetime(value: Any, field: str) -> str:
        if not isinstance(value, str):
            raise AuthorityIssuerError(f"{field}_MUST_BE_STRING")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AuthorityIssuerError(f"{field}_INVALID") from exc
        if parsed.tzinfo is None:
            raise AuthorityIssuerError(f"{field}_MUST_BE_TIMEZONE_AWARE")
        rendered = parsed.isoformat(
            timespec="microseconds" if parsed.microsecond else "seconds"
        )
        if rendered.endswith("+00:00"):
            rendered = rendered[:-6] + "Z"
        return rendered

    @classmethod
    def _canonical_bytes(cls, envelope: Mapping[str, Any]) -> bytes:
        data = deepcopy(dict(envelope))
        data.pop("authority_proof", None)
        data.pop("transport_metadata", None)
        data.pop("model_provider_metadata", None)

        data["issued_at"] = cls._canonical_datetime(data.get("issued_at"), "TASK_ISSUED_AT")
        data["expires_at"] = cls._canonical_datetime(data.get("expires_at"), "TASK_EXPIRES_AT")
        lease = data.get("execution_lease")
        if not isinstance(lease, dict):
            raise AuthorityIssuerError("EXECUTION_LEASE_REQUIRED")
        lease["issued_at"] = cls._canonical_datetime(
            lease.get("issued_at"),
            "LEASE_ISSUED_AT",
        )
        lease["expires_at"] = cls._canonical_datetime(
            lease.get("expires_at"),
            "LEASE_EXPIRES_AT",
        )

        return json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
