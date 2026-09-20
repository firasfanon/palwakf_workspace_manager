from __future__ import annotations

import hashlib
import json
import math

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ServiceLevelTargetV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str = Field(min_length=3, max_length=160)
    min_samples: int = Field(ge=1, le=100_000)
    min_success_ratio: float = Field(ge=0.0, le=1.0)
    max_p95_latency_ms: float = Field(gt=0)
    max_p99_latency_ms: float = Field(gt=0)
    min_throughput_rps: float = Field(gt=0)
    max_memory_delta_bytes: int = Field(ge=0)
    min_overload_rejection_ratio: float = Field(ge=0.0, le=1.0)
    required_metric_names: tuple[str, ...] = ()
    require_store_healthy: bool = True

    @model_validator(mode="after")
    def validate_target(self) -> ServiceLevelTargetV1:
        if self.max_p99_latency_ms < self.max_p95_latency_ms:
            raise ValueError("SLO_P99_TARGET_MUST_NOT_BE_STRICTER_THAN_P95")
        if len(set(self.required_metric_names)) != len(self.required_metric_names):
            raise ValueError("SLO_REQUIRED_METRIC_NAMES_MUST_BE_UNIQUE")
        if any(not item.strip() for item in self.required_metric_names):
            raise ValueError("SLO_REQUIRED_METRIC_NAME_INVALID")
        return self


class ServiceLevelMeasurementV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    latencies_ms: tuple[float, ...]
    successes: int = Field(ge=0)
    failures: int = Field(ge=0)
    concurrency: int = Field(ge=1)
    queue_capacity: int = Field(ge=1)
    worker_count: int = Field(ge=1)
    elapsed_ms: float = Field(gt=0)
    memory_delta_bytes: int = Field(ge=0)
    overload_attempts: int = Field(ge=0)
    overload_rejections: int = Field(ge=0)
    store_healthy: bool
    observed_metric_names: tuple[str, ...]

    @model_validator(mode="after")
    def validate_measurement(self) -> ServiceLevelMeasurementV1:
        if not self.latencies_ms:
            raise ValueError("SLO_LATENCY_SAMPLES_REQUIRED")
        if any(value < 0 for value in self.latencies_ms):
            raise ValueError("SLO_LATENCY_SAMPLE_NEGATIVE")
        if self.successes + self.failures != len(self.latencies_ms):
            raise ValueError("SLO_SAMPLE_COUNT_MISMATCH")
        if self.overload_rejections > self.overload_attempts:
            raise ValueError("SLO_OVERLOAD_REJECTIONS_EXCEED_ATTEMPTS")
        if len(set(self.observed_metric_names)) != len(self.observed_metric_names):
            raise ValueError("SLO_OBSERVED_METRIC_NAMES_MUST_BE_UNIQUE")
        return self


class ServiceLevelEvaluationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    target_id: str
    sample_count: int
    successes: int
    failures: int
    success_ratio: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    throughput_rps: float
    memory_delta_bytes: int
    concurrency: int
    queue_capacity: int
    worker_count: int
    overload_attempts: int
    overload_rejections: int
    overload_rejection_ratio: float
    store_healthy: bool
    observed_metric_names: tuple[str, ...]
    gaps: tuple[str, ...]
    passed: bool
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_integrity(self) -> ServiceLevelEvaluationV1:
        payload = self.model_dump(mode="json", exclude={"evidence_sha256"})
        expected = _hash_payload(payload)
        if self.evidence_sha256 != expected:
            raise ValueError("SLO_EVIDENCE_HASH_MISMATCH")
        if self.passed and self.gaps:
            raise ValueError("SLO_PASS_REQUIRES_ZERO_GAPS")
        return self


def _hash_payload(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _percentile(values: tuple[float, ...], percentile: float) -> float:
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return float(ordered[rank - 1])


def evaluate_service_level(
    *,
    target: ServiceLevelTargetV1,
    measurement: ServiceLevelMeasurementV1,
) -> ServiceLevelEvaluationV1:
    sample_count = len(measurement.latencies_ms)
    success_ratio = measurement.successes / sample_count
    p50 = _percentile(measurement.latencies_ms, 0.50)
    p95 = _percentile(measurement.latencies_ms, 0.95)
    p99 = _percentile(measurement.latencies_ms, 0.99)
    throughput_rps = sample_count / (measurement.elapsed_ms / 1000.0)
    overload_ratio = (
        measurement.overload_rejections / measurement.overload_attempts
        if measurement.overload_attempts
        else 0.0
    )

    gaps: list[str] = []
    if sample_count < target.min_samples:
        gaps.append("SLO_MIN_SAMPLE_COUNT_NOT_MET")
    if success_ratio < target.min_success_ratio:
        gaps.append("SLO_SUCCESS_RATIO_NOT_MET")
    if p95 > target.max_p95_latency_ms:
        gaps.append("SLO_P95_LATENCY_NOT_MET")
    if p99 > target.max_p99_latency_ms:
        gaps.append("SLO_P99_LATENCY_NOT_MET")
    if throughput_rps < target.min_throughput_rps:
        gaps.append("SLO_THROUGHPUT_NOT_MET")
    if measurement.memory_delta_bytes > target.max_memory_delta_bytes:
        gaps.append("SLO_MEMORY_DELTA_NOT_MET")
    if target.require_store_healthy and not measurement.store_healthy:
        gaps.append("SLO_STORE_HEALTH_NOT_MET")
    if measurement.overload_attempts == 0:
        gaps.append("SLO_OVERLOAD_PROOF_REQUIRED")
    elif overload_ratio < target.min_overload_rejection_ratio:
        gaps.append("SLO_OVERLOAD_REJECTION_RATIO_NOT_MET")

    observed = set(measurement.observed_metric_names)
    for required in target.required_metric_names:
        if required not in observed:
            gaps.append(f"SLO_REQUIRED_METRIC_MISSING:{required}")

    payload = {
        "target_id": target.target_id,
        "sample_count": sample_count,
        "successes": measurement.successes,
        "failures": measurement.failures,
        "success_ratio": success_ratio,
        "p50_latency_ms": p50,
        "p95_latency_ms": p95,
        "p99_latency_ms": p99,
        "throughput_rps": throughput_rps,
        "memory_delta_bytes": measurement.memory_delta_bytes,
        "concurrency": measurement.concurrency,
        "queue_capacity": measurement.queue_capacity,
        "worker_count": measurement.worker_count,
        "overload_attempts": measurement.overload_attempts,
        "overload_rejections": measurement.overload_rejections,
        "overload_rejection_ratio": overload_ratio,
        "store_healthy": measurement.store_healthy,
        "observed_metric_names": list(measurement.observed_metric_names),
        "gaps": gaps,
        "passed": not gaps,
    }
    return ServiceLevelEvaluationV1(
        target_id=target.target_id,
        sample_count=sample_count,
        successes=measurement.successes,
        failures=measurement.failures,
        success_ratio=success_ratio,
        p50_latency_ms=p50,
        p95_latency_ms=p95,
        p99_latency_ms=p99,
        throughput_rps=throughput_rps,
        memory_delta_bytes=measurement.memory_delta_bytes,
        concurrency=measurement.concurrency,
        queue_capacity=measurement.queue_capacity,
        worker_count=measurement.worker_count,
        overload_attempts=measurement.overload_attempts,
        overload_rejections=measurement.overload_rejections,
        overload_rejection_ratio=overload_ratio,
        store_healthy=measurement.store_healthy,
        observed_metric_names=measurement.observed_metric_names,
        gaps=tuple(gaps),
        passed=not gaps,
        evidence_sha256=_hash_payload(payload),
    )
