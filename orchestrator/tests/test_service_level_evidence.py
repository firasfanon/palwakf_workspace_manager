from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_contracts import (
    ClientPrincipal,
    ConnectedDispatchRequest,
    ServiceScope,
)
from palwakf_orchestrator.connected_service import ConnectedApplicationService
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    CreateOperatorTaskRequest,
    TaskCapabilityRequest,
)
from palwakf_orchestrator.operator_service import OperatorService
from palwakf_orchestrator.persistence import MemoryStateStore
from palwakf_orchestrator.service_level_evidence import (
    ServiceLevelEvaluationV1,
    ServiceLevelMeasurementV1,
    ServiceLevelTargetV1,
    evaluate_service_level,
)
from tests.test_service import FULL_HEAD, build_service


class AcceptingVerifier:
    def verify(self, branch: str, expected_head: str) -> str:
        return expected_head


def target() -> ServiceLevelTargetV1:
    return ServiceLevelTargetV1(
        target_id="L5_LOCAL_RUNTIME_SLO_V1",
        min_samples=5,
        min_success_ratio=1.0,
        max_p95_latency_ms=100.0,
        max_p99_latency_ms=250.0,
        min_throughput_rps=10.0,
        max_memory_delta_bytes=64 * 1024 * 1024,
        min_overload_rejection_ratio=1.0,
        required_metric_names=(
            "http_probe_latency_ms",
            "queue_available_slots",
            "store_healthy",
        ),
    )


def measurement(**updates: object) -> ServiceLevelMeasurementV1:
    values: dict[str, object] = {
        "latencies_ms": (5.0, 7.0, 9.0, 11.0, 13.0),
        "successes": 5,
        "failures": 0,
        "concurrency": 4,
        "queue_capacity": 2,
        "worker_count": 1,
        "elapsed_ms": 100.0,
        "memory_measurement_available": True,
        "memory_measurement_source": "test-fixture",
        "memory_delta_bytes": 1024,
        "overload_attempts": 1,
        "overload_rejections": 1,
        "store_healthy": True,
        "observed_metric_names": (
            "http_probe_latency_ms",
            "queue_available_slots",
            "store_healthy",
        ),
    }
    values.update(updates)
    return ServiceLevelMeasurementV1.model_validate(values)


def test_passing_measurement_produces_hashed_slo_evidence() -> None:
    result = evaluate_service_level(target=target(), measurement=measurement())

    assert result.passed is True
    assert result.gaps == ()
    assert result.sample_count == 5
    assert result.success_ratio == 1.0
    assert result.p50_latency_ms == 9.0
    assert result.p95_latency_ms == 13.0
    assert result.p99_latency_ms == 13.0
    assert result.throughput_rps == 50.0
    assert result.memory_measurement_available is True
    assert result.memory_measurement_source == "test-fixture"
    assert result.memory_delta_bytes == 1024
    assert result.overload_rejection_ratio == 1.0
    assert len(result.evidence_sha256) == 64


@pytest.mark.parametrize(
    ("updates", "expected_gap"),
    [
        (
            {
                "latencies_ms": (5.0, 7.0, 9.0, 11.0),
                "successes": 4,
            },
            "SLO_MIN_SAMPLE_COUNT_NOT_MET",
        ),
        (
            {
                "successes": 4,
                "failures": 1,
            },
            "SLO_SUCCESS_RATIO_NOT_MET",
        ),
        (
            {
                "latencies_ms": (5.0, 7.0, 9.0, 11.0, 300.0),
            },
            "SLO_P95_LATENCY_NOT_MET",
        ),
        (
            {
                "elapsed_ms": 1000.0,
            },
            "SLO_THROUGHPUT_NOT_MET",
        ),
        (
            {
                "memory_delta_bytes": 65 * 1024 * 1024,
            },
            "SLO_MEMORY_DELTA_NOT_MET",
        ),
        (
            {
                "store_healthy": False,
            },
            "SLO_STORE_HEALTH_NOT_MET",
        ),
        (
            {
                "overload_attempts": 0,
                "overload_rejections": 0,
            },
            "SLO_OVERLOAD_PROOF_REQUIRED",
        ),
        (
            {
                "observed_metric_names": (
                    "http_probe_latency_ms",
                    "store_healthy",
                ),
            },
            "SLO_REQUIRED_METRIC_MISSING:queue_available_slots",
        ),
    ],
)
def test_each_required_slo_gate_fails_closed(
    updates: dict[str, object],
    expected_gap: str,
) -> None:
    result = evaluate_service_level(
        target=target(),
        measurement=measurement(**updates),
    )

    assert result.passed is False
    assert expected_gap in result.gaps


def test_measurement_rejects_inconsistent_counts() -> None:
    with pytest.raises(ValidationError, match="SLO_SAMPLE_COUNT_MISMATCH"):
        measurement(successes=4, failures=0)


def test_measurement_fails_closed_when_memory_measurement_is_unavailable() -> None:
    with pytest.raises(ValidationError):
        measurement(memory_measurement_available=False)


def test_measurement_requires_nonempty_memory_measurement_source() -> None:
    with pytest.raises(ValidationError):
        measurement(memory_measurement_source="")


def test_evaluation_hash_tampering_is_rejected() -> None:
    result = evaluate_service_level(target=target(), measurement=measurement())
    raw = result.model_dump(mode="json")
    raw["p95_latency_ms"] = 99.0

    with pytest.raises(ValidationError, match="SLO_EVIDENCE_HASH_MISMATCH"):
        ServiceLevelEvaluationV1.model_validate(raw)


def _dispatch_request(task_id: str) -> ConnectedDispatchRequest:
    task = CreateOperatorTaskRequest(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        repository="firasfanon/palwakf_workspace_manager",
        branch="agent/workspace-manager-foundation-v1",
        expected_head=FULL_HEAD,
        authority_reference="AUTHORITY://L5-003",
        prompt="Return one bounded read-only result.",
        constraints=["NO_PRODUCTION", "NO_DATABASE_WRITE"],
        sandbox="read-only",
        max_turns=1,
        timeout_seconds=60,
        idempotency_key=f"l5-003-{task_id.lower()}",
    )
    plan = TaskCapabilityRequest(
        task_id=task_id,
        project_id="PALWAKF_WORKSPACE_MANAGER",
        task_type="read-only-probe",
        mutation_class="read-only",
        environment="local",
        data_classification="internal",
        acceptance_requirements=["bounded queue evidence"],
    )
    return ConnectedDispatchRequest(task=task, tool_plan=plan)


def _principal() -> ClientPrincipal:
    return ClientPrincipal(
        client_id="l5-003-capacity-test",
        scopes=frozenset(ServiceScope),
    )


@pytest.mark.asyncio
async def test_bounded_queue_rejects_overload_without_authority_expansion(
    tmp_path: Path,
) -> None:
    settings = Settings(
        workspace_root=tmp_path,
        queue_capacity=2,
        worker_count=1,
    )
    store = MemoryStateStore()
    operator = OperatorService(
        tmp_path,
        orchestrator=build_service(tmp_path),
        verifier=AcceptingVerifier(),
        automatic_agents_available=True,
        state_store=store,
    )
    connected = ConnectedApplicationService(
        settings,
        operator,
        store,
        authentication_configured=True,
    )

    await connected.dispatch(
        _dispatch_request("L5_CAPACITY_001"),
        _principal(),
        transport="http",
    )
    await connected.dispatch(
        _dispatch_request("L5_CAPACITY_002"),
        _principal(),
        transport="http",
    )

    assert connected.queue_snapshot().available_slots == 0
    with pytest.raises(GovernanceError, match="bounded dispatch queue is full"):
        await connected.dispatch(
            _dispatch_request("L5_CAPACITY_003"),
            _principal(),
            transport="http",
        )

    snapshot = connected.queue_snapshot()
    assert snapshot.capacity == 2
    assert snapshot.queued == 2
    assert snapshot.running == 0
    assert snapshot.available_slots == 0
