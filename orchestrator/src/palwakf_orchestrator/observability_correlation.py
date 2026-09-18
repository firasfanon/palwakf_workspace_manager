from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SourceSystem = Literal["WORKSPACE_MANAGER", "AGENTIC_AI", "MIND_ASSISTANT", "TARGET_PROJECT"]

SYSTEM_IDS: tuple[SourceSystem, ...] = (
    "WORKSPACE_MANAGER",
    "AGENTIC_AI",
    "MIND_ASSISTANT",
    "TARGET_PROJECT",
)
_SECRET_PATTERNS = (
    (re.compile(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/=-]{12,}"), r"\1 <REDACTED>"),
    (re.compile(r"\b(?:ghp|github_pat|sk|xox[baprs])_[A-Za-z0-9_-]{12,}\b"), "<REDACTED_TOKEN>"),
    (
        re.compile(
            r"(?i)(api[_-]?key|secret|token|password|passwd|authorization)"
            r"\s*[:=]\s*[^\s,;]+"
        ),
        r"\1=<REDACTED>",
    ),
)


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def redact_text(value: str) -> tuple[str, bool]:
    redacted = value
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted, redacted != value


class TraceIdentityV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    project_id: str = Field(min_length=2, max_length=160)
    task_id: str = Field(min_length=2, max_length=160)
    run_id: str = Field(min_length=2, max_length=160)
    authorization_id: str = Field(min_length=2, max_length=200)
    agent_id: str = Field(min_length=2, max_length=200)
    model_provider_id: str = Field(min_length=1, max_length=160)
    execution_provider_id: str = Field(min_length=2, max_length=160)
    contract_id: str = Field(min_length=2, max_length=200)

    def trace_id(self) -> str:
        return _canonical_hash(self.model_dump(mode="json"))[:32]


class CorrelationSpanV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    parent_span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    source_system: Literal["WORKSPACE_MANAGER", "AGENTIC_AI", "MIND_ASSISTANT", "TARGET_PROJECT"]
    name: str = Field(min_length=2, max_length=200)
    identity: TraceIdentityV1
    started_at: datetime
    attributes: dict[str, str] = Field(default_factory=dict)
    export_policy: Literal["LOCAL_ONLY_NO_REMOTE_EXPORT"] = "LOCAL_ONLY_NO_REMOTE_EXPORT"

    @model_validator(mode="after")
    def _validate_trace_binding(self) -> CorrelationSpanV1:
        if self.trace_id != self.identity.trace_id():
            raise ValueError("OBSERVABILITY_TRACE_IDENTITY_MISMATCH")
        if self.parent_span_id == self.span_id:
            raise ValueError("OBSERVABILITY_SPAN_SELF_PARENT")
        return self


class TelemetryLogV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    severity: Literal["DEBUG", "INFO", "WARN", "ERROR"]
    message: str
    attributes: dict[str, str]
    redaction_applied: bool
    remote_export_allowed: Literal[False] = False


class TelemetryMetricV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    name: str = Field(min_length=2, max_length=200)
    value: float
    unit: str = "1"
    attributes: dict[str, str] = Field(default_factory=dict)
    remote_export_allowed: Literal[False] = False


class CorrelationTraceV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    identity: TraceIdentityV1
    spans: tuple[CorrelationSpanV1, ...]
    logs: tuple[TelemetryLogV1, ...] = ()
    metrics: tuple[TelemetryMetricV1, ...] = ()

    @model_validator(mode="after")
    def _validate_chain(self) -> CorrelationTraceV1:
        trace_id = self.identity.trace_id()
        known: set[str] = set()
        for index, span in enumerate(self.spans):
            if span.trace_id != trace_id or span.identity != self.identity:
                raise ValueError("OBSERVABILITY_TRACE_CONTINUITY_BROKEN")
            if index == 0 and span.parent_span_id is not None:
                raise ValueError("OBSERVABILITY_ROOT_SPAN_HAS_PARENT")
            if index and span.parent_span_id not in known:
                raise ValueError("OBSERVABILITY_PARENT_SPAN_UNKNOWN")
            known.add(span.span_id)
        if any(item.trace_id != trace_id for item in self.logs):
            raise ValueError("OBSERVABILITY_EVENT_TRACE_MISMATCH")
        if any(item.trace_id != trace_id for item in self.metrics):
            raise ValueError("OBSERVABILITY_EVENT_TRACE_MISMATCH")
        return self


def build_span(
    *,
    identity: TraceIdentityV1,
    source_system: SourceSystem,
    name: str,
    ordinal: int,
    parent_span_id: str | None = None,
    attributes: dict[str, str] | None = None,
) -> CorrelationSpanV1:
    if source_system not in SYSTEM_IDS:
        raise ValueError("OBSERVABILITY_SOURCE_SYSTEM_UNKNOWN")
    trace_id = identity.trace_id()
    span_id = _canonical_hash(
        {"trace_id": trace_id, "source_system": source_system, "name": name, "ordinal": ordinal}
    )[:16]
    sanitized: dict[str, str] = {}
    for key, value in (attributes or {}).items():
        clean, _ = redact_text(str(value))
        sanitized[str(key)] = clean
    return CorrelationSpanV1(
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        source_system=source_system,
        name=name,
        identity=identity,
        started_at=datetime.now(UTC),
        attributes=sanitized,
    )


def build_log(
    *,
    span: CorrelationSpanV1,
    severity: Literal["DEBUG", "INFO", "WARN", "ERROR"],
    message: str,
    attributes: dict[str, str] | None = None,
) -> TelemetryLogV1:
    clean_message, changed = redact_text(message)
    clean_attributes: dict[str, str] = {}
    for key, value in (attributes or {}).items():
        clean, item_changed = redact_text(str(value))
        clean_attributes[str(key)] = clean
        changed = changed or item_changed
    return TelemetryLogV1(
        trace_id=span.trace_id,
        span_id=span.span_id,
        severity=severity,
        message=clean_message,
        attributes=clean_attributes,
        redaction_applied=changed,
    )


def build_metric(
    *, identity: TraceIdentityV1, name: str, value: float, unit: str = "1"
) -> TelemetryMetricV1:
    return TelemetryMetricV1(
        trace_id=identity.trace_id(),
        name=name,
        value=value,
        unit=unit,
        attributes={
            "project_id": identity.project_id,
            "task_id": identity.task_id,
            "run_id": identity.run_id,
        },
    )


def otel_attributes(identity: TraceIdentityV1) -> dict[str, str]:
    return {
        "palwakf.project.id": identity.project_id,
        "palwakf.task.id": identity.task_id,
        "palwakf.run.id": identity.run_id,
        "palwakf.authorization.id": identity.authorization_id,
        "palwakf.agent.id": identity.agent_id,
        "palwakf.model_provider.id": identity.model_provider_id,
        "palwakf.execution_provider.id": identity.execution_provider_id,
        "palwakf.contract.id": identity.contract_id,
        "palwakf.remote_export": "false",
    }
