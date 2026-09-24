
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from palwakf_orchestrator.portfolio_intelligence_contracts import (
    RegistryEntity,
    SourceHealthItem,
    SourceHealthState,
)


@dataclass(frozen=True)
class _ReadResult:
    data: Any | None
    freshness: str
    observed_at: datetime | None


@dataclass(frozen=True)
class LivePortfolioRuntimeProjection:
    source_health: list[SourceHealthItem]
    skills: list[RegistryEntity]
    capabilities: list[RegistryEntity]
    agents: list[RegistryEntity]
    providers: list[RegistryEntity]
    provenance: list[str]


class PortfolioLiveRuntimeAdapter:
    def __init__(
        self,
        *,
        mind_base_url: str,
        agentic_base_url: str,
        timeout_seconds: float = 0.8,
    ) -> None:
        self._mind = mind_base_url.rstrip("/")
        self._agentic = agentic_base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._last_good: dict[str, tuple[datetime, Any]] = {}

    def _get(self, key: str, url: str) -> _ReadResult:
        now = datetime.now(UTC)

        try:
            response = httpx.get(url, timeout=self._timeout)
            response.raise_for_status()
            payload = response.json()
            self._last_good[key] = (now, payload)

            return _ReadResult(
                data=payload,
                freshness="LIVE",
                observed_at=now,
            )
        except Exception:
            cached = self._last_good.get(key)

            if cached is None:
                return _ReadResult(
                    data=None,
                    freshness="UNAVAILABLE",
                    observed_at=None,
                )

            observed_at, payload = cached

            return _ReadResult(
                data=payload,
                freshness="LAST_VERIFIED_CACHE",
                observed_at=observed_at,
            )

    def snapshot(self) -> LivePortfolioRuntimeProjection:
        mind_health = self._get(
            "mind_health",
            f"{self._mind}/health",
        )
        mind_ready = self._get(
            "mind_ready",
            f"{self._mind}/ready",
        )
        mind_skills = self._get(
            "mind_skills",
            f"{self._mind}/v1/skills",
        )
        mind_capabilities = self._get(
            "mind_capabilities",
            f"{self._mind}/v1/capabilities",
        )
        mind_drive = self._get(
            "mind_drive",
            f"{self._mind}/v1/system/connector",
        )

        agentic_health = self._get(
            "agentic_health",
            f"{self._agentic}/health",
        )
        agentic_agents = self._get(
            "agentic_agents",
            f"{self._agentic}/api/agents",
        )

        mh = (
            mind_health.data
            if isinstance(mind_health.data, dict)
            else {}
        )
        mr = (
            mind_ready.data
            if isinstance(mind_ready.data, dict)
            else {}
        )

        mind_ok = (
            mh.get("status") == "ok"
            and mh.get("mutation_mode") == "READ_ONLY"
            and mr.get("status") == "ready"
        )

        mind_freshness = (
            "LIVE"
            if (
                mind_health.freshness == "LIVE"
                and mind_ready.freshness == "LIVE"
            )
            else "LAST_VERIFIED_CACHE"
            if mind_health.data is not None
            else "UNAVAILABLE"
        )

        mind_state = (
            SourceHealthState.healthy
            if mind_ok and mind_freshness == "LIVE"
            else SourceHealthState.degraded
            if mind_ok
            else SourceHealthState.unavailable
        )

        ah = (
            agentic_health.data
            if isinstance(agentic_health.data, dict)
            else {}
        )

        agentic_ok = (
            ah.get("safety_ok") is True
            and ah.get("platform_mutation_enabled") is False
            and ah.get("database_access_enabled") is False
        )

        agentic_state = (
            SourceHealthState.healthy
            if (
                agentic_ok
                and agentic_health.freshness == "LIVE"
            )
            else SourceHealthState.degraded
            if agentic_ok
            else SourceHealthState.unavailable
        )

        drive = (
            mind_drive.data
            if isinstance(mind_drive.data, dict)
            else {}
        )

        drive_ready = (
            drive.get("state") == "READY"
            and drive.get("writes_enabled") is False
        )

        drive_mode = str(
            drive.get("mode") or "UNKNOWN"
        ).upper()

        live_drive = drive_mode in {
            "DRIVE_REST",
            "GOOGLE_DRIVE_REST",
            "LIVE_DRIVE_READ_ONLY",
        }

        if (
            drive_ready
            and live_drive
            and mind_drive.freshness == "LIVE"
        ):
            drive_state = SourceHealthState.healthy
        elif drive_ready or mind_drive.data is not None:
            drive_state = SourceHealthState.degraded
        else:
            drive_state = SourceHealthState.unavailable

        source_health = [
            SourceHealthItem(
                source_id="MIND_RUNTIME",
                label_ar="Mind Assistant — واقع التشغيل",
                state=mind_state,
                freshness=mind_freshness,
                detail_ar=(
                    "Mind متصل بعقد READ_ONLY وجاهزية مثبتة."
                    if mind_state == SourceHealthState.healthy
                    else
                    "تعذر إثبات القراءة الحية بالكامل؛ "
                    "تُحفظ آخر قراءة موثقة إن وجدت."
                ),
                authority="PALWAKF_MIND_ASSISTANT_RUNTIME_READ_ONLY",
                observed_at=mind_health.observed_at,
            ),
            SourceHealthItem(
                source_id="AGENTIC_RUNTIME",
                label_ar="Agentic AI — واقع التشغيل",
                state=agentic_state,
                freshness=agentic_health.freshness,
                detail_ar=(
                    "Agentic متصل وsafety_ok مع منع platform/database mutation."
                    if agentic_state == SourceHealthState.healthy
                    else
                    "حالة Agentic الحية غير مكتملة."
                ),
                authority="PALWAKF_AGENTIC_RUNTIME_READ_ONLY",
                observed_at=agentic_health.observed_at,
            ),
            SourceHealthItem(
                source_id="WORKSPACE_DRIVE_SOVEREIGN",
                label_ar="Workspace Drive السيادي",
                state=drive_state,
                freshness=(
                    f"{mind_drive.freshness}:{drive_mode}"
                ),
                detail_ar=(
                    "Drive live read-only مثبت."
                    if drive_state == SourceHealthState.healthy
                    else
                    "Connector متاح لكن وضعه ليس دليلاً على Drive live؛ "
                    f"mode={drive_mode}."
                ),
                authority="WORKSPACE_DRIVE_SOVEREIGN",
                observed_at=mind_drive.observed_at,
            ),
        ]

        skills = []

        raw_skills = (
            mind_skills.data
            if isinstance(mind_skills.data, list)
            else []
        )

        for raw in raw_skills:
            if not isinstance(raw, dict):
                continue

            skill_id = str(
                raw.get("skill_id") or "UNKNOWN_SKILL"
            )

            provenance = str(
                raw.get("provenance_ref") or ""
            )

            skills.append(
                RegistryEntity(
                    entity_id=f"MIND_SKILL_{skill_id}",
                    name_ar=skill_id,
                    category="SKILL",
                    lifecycle=str(
                        raw.get("status") or "OBSERVED"
                    ),
                    status="OBSERVED",
                    description_ar=(
                        f"level={raw.get('level', 'UNKNOWN')} ? "
                        f"owner={raw.get('owner_scope', 'UNKNOWN')}"
                    ),
                    owner=str(
                        raw.get("owner_scope")
                        or "PALWAKF_MIND_ASSISTANT"
                    ),
                    evidence_refs=(
                        [provenance]
                        if provenance
                        else []
                    ),
                )
            )

        capabilities = []

        raw_caps = (
            mind_capabilities.data
            if isinstance(
                mind_capabilities.data,
                list,
            )
            else []
        )

        for raw in raw_caps:
            if not isinstance(raw, dict):
                continue

            capability_id = str(
                raw.get("capability_id")
                or "UNKNOWN_CAPABILITY"
            )

            capabilities.append(
                RegistryEntity(
                    entity_id=(
                        f"MIND_CAPABILITY_{capability_id}"
                    ),
                    name_ar=str(
                        raw.get("name")
                        or capability_id
                    ),
                    category="CAPABILITY",
                    lifecycle="MIND_RUNTIME_IMPORT",
                    status="OBSERVED",
                    description_ar=(
                        f"risk={raw.get('risk_class', 'UNKNOWN')} ? "
                        f"mutation={raw.get('mutation_class', 'UNKNOWN')} ? "
                        f"source_mode={raw.get('source_mode', 'UNKNOWN')}"
                    ),
                    owner="PALWAKF_MIND_ASSISTANT",
                )
            )

        agents = []

        raw_agents = (
            agentic_agents.data
            if isinstance(
                agentic_agents.data,
                list,
            )
            else []
        )

        for raw in raw_agents:
            if not isinstance(raw, dict):
                continue

            agent_id = str(
                raw.get("id")
                or "UNKNOWN_AGENT"
            )

            agents.append(
                RegistryEntity(
                    entity_id=(
                        f"AGENTIC_AGENT_{agent_id}"
                    ),
                    name_ar=str(
                        raw.get("name_ar")
                        or agent_id
                    ),
                    category="AGENT",
                    lifecycle=str(
                        raw.get("lifecycle")
                        or "OBSERVED"
                    ),
                    status="OBSERVED",
                    description_ar=(
                        "authority="
                        f"{raw.get('authority', 'UNKNOWN')}"
                    ),
                    owner="PALWAKF_AGENTIC_AI",
                )
            )

        providers = [
            RegistryEntity(
                entity_id="PROVIDER_MIND_RUNTIME",
                name_ar="PalWakf Mind Assistant",
                category="PROVIDER",
                lifecycle="LIVE_RUNTIME",
                status=mind_state.value,
                description_ar=(
                    "مزود معرفة ومراجعة مؤسسية."
                ),
                owner="PALWAKF_MIND_ASSISTANT",
            ),
            RegistryEntity(
                entity_id="PROVIDER_AGENTIC_RUNTIME",
                name_ar="PalWakf Agentic AI",
                category="PROVIDER",
                lifecycle="LIVE_RUNTIME",
                status=agentic_state.value,
                description_ar=(
                    "مزود الوكلاء والتنفيذ المحكوم."
                ),
                owner="PALWAKF_AGENTIC_AI",
            ),
        ]

        return LivePortfolioRuntimeProjection(
            source_health=source_health,
            skills=skills,
            capabilities=capabilities,
            agents=agents,
            providers=providers,
            provenance=[
                "MIND_RUNTIME_READ_ONLY_ADAPTER",
                "AGENTIC_RUNTIME_READ_ONLY_ADAPTER",
                "WORKSPACE_DRIVE_STATUS_VIA_MIND_CONNECTOR",
                "LAST_VERIFIED_RUNTIME_CACHE_IS_DERIVED_NOT_SOVEREIGN",
            ],
        )
