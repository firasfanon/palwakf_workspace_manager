from __future__ import annotations

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.observability_correlation import (
    CorrelationTraceV1,
    TraceIdentityV1,
    build_log,
    build_metric,
    build_span,
    otel_attributes,
)


def _identity(**overrides) -> TraceIdentityV1:
    data = {
        "project_id": "PALWAKF_WORKSPACE_MANAGER",
        "task_id": "PREL5-038",
        "run_id": "run-prel5-038-001",
        "authorization_id": "AUTH-PREL5-038",
        "agent_id": "coding_builder_agentic_v1",
        "model_provider_id": "ollama",
        "execution_provider_id": "PALWAKF_NATIVE_AGENT",
        "contract_id": "PALWAKF_INTERSYSTEM_CONTRACT_V1",
    }
    data.update(overrides)
    return TraceIdentityV1.model_validate(data)


def test_otel_attributes_include_all_required_correlation_dimensions() -> None:
    attrs = otel_attributes(_identity())
    assert set(attrs) == {
        "palwakf.project.id",
        "palwakf.task.id",
        "palwakf.run.id",
        "palwakf.authorization.id",
        "palwakf.agent.id",
        "palwakf.model_provider.id",
        "palwakf.execution_provider.id",
        "palwakf.contract.id",
        "palwakf.remote_export",
    }
    assert attrs["palwakf.remote_export"] == "false"


def test_four_system_trace_continuity() -> None:
    identity = _identity()
    workspace = build_span(
        identity=identity,
        source_system="WORKSPACE_MANAGER",
        name="workspace.dispatch",
        ordinal=0,
    )
    agentic = build_span(
        identity=identity,
        source_system="AGENTIC_AI",
        name="agentic.execute",
        ordinal=1,
        parent_span_id=workspace.span_id,
    )
    mind = build_span(
        identity=identity,
        source_system="MIND_ASSISTANT",
        name="mind.learning_review",
        ordinal=2,
        parent_span_id=agentic.span_id,
    )
    target = build_span(
        identity=identity,
        source_system="TARGET_PROJECT",
        name="target.readback",
        ordinal=3,
        parent_span_id=mind.span_id,
    )
    trace = CorrelationTraceV1(identity=identity, spans=(workspace, agentic, mind, target))
    assert len({span.trace_id for span in trace.spans}) == 1
    assert [span.source_system for span in trace.spans] == [
        "WORKSPACE_MANAGER",
        "AGENTIC_AI",
        "MIND_ASSISTANT",
        "TARGET_PROJECT",
    ]


def test_logs_are_redacted_and_never_remote_exported() -> None:
    identity = _identity()
    span = build_span(
        identity=identity,
        source_system="AGENTIC_AI",
        name="agentic.review",
        ordinal=0,
    )
    log = build_log(
        span=span,
        severity="INFO",
        message="token=ghp_SYNTHETIC123456789 password=synthetic_password",
        attributes={"authorization": "Bearer abcdefghijklmnop"},
    )
    assert log.redaction_applied is True
    payload = log.model_dump_json()
    assert "ghp_SYNTHETIC" not in payload
    assert "synthetic_password" not in payload
    assert "abcdefghijklmnop" not in payload
    assert log.remote_export_allowed is False


def test_metric_and_span_are_local_only_and_trace_bound() -> None:
    identity = _identity()
    span = build_span(
        identity=identity,
        source_system="WORKSPACE_MANAGER",
        name="workspace.acceptance",
        ordinal=0,
    )
    metric = build_metric(identity=identity, name="palwakf.acceptance.pass", value=1)
    trace = CorrelationTraceV1(identity=identity, spans=(span,), metrics=(metric,))
    assert trace.metrics[0].trace_id == identity.trace_id()
    assert trace.spans[0].export_policy == "LOCAL_ONLY_NO_REMOTE_EXPORT"
    assert trace.metrics[0].remote_export_allowed is False


def test_unknown_parent_fails_closed() -> None:
    identity = _identity()
    root = build_span(
        identity=identity,
        source_system="WORKSPACE_MANAGER",
        name="workspace.root",
        ordinal=0,
    )
    child = build_span(
        identity=identity,
        source_system="AGENTIC_AI",
        name="agentic.child",
        ordinal=1,
        parent_span_id="f" * 16,
    )
    with pytest.raises(ValidationError, match="OBSERVABILITY_PARENT_SPAN_UNKNOWN"):
        CorrelationTraceV1(identity=identity, spans=(root, child))


def test_identity_drift_breaks_trace_continuity() -> None:
    first = _identity()
    second = _identity(task_id="PREL5-999")
    span = build_span(
        identity=second,
        source_system="MIND_ASSISTANT",
        name="mind.review",
        ordinal=0,
    )
    with pytest.raises(ValidationError, match="OBSERVABILITY_TRACE_CONTINUITY_BROKEN"):
        CorrelationTraceV1(identity=first, spans=(span,))


def test_unknown_source_system_is_rejected() -> None:
    with pytest.raises(ValueError, match="OBSERVABILITY_SOURCE_SYSTEM_UNKNOWN"):
        build_span(
            identity=_identity(),
            source_system="UNKNOWN",
            name="unknown.span",
            ordinal=0,
        )
