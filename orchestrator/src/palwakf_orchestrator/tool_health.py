from __future__ import annotations

from datetime import UTC, datetime

from palwakf_orchestrator.capability_router import (
    CapabilityRegistry,
    workspace_manager_profile,
)
from palwakf_orchestrator.connected_contracts import (
    HealthFact,
    ToolHealthAlert,
    ToolHealthAlertSeverity,
    ToolOperationalHealth,
    ValueProvenance,
)
from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.persistence import StateStore
from palwakf_orchestrator.provider_contracts import RoleAuthority


def _unknown(note: str = "Provider does not expose a verified value") -> HealthFact:
    return HealthFact(
        value=None,
        provenance=ValueProvenance.not_exposed_by_provider,
        note=note,
    )


class ToolHealthService:
    def __init__(
        self,
        store: StateStore,
        registry: CapabilityRegistry | None = None,
    ) -> None:
        self._store = store
        self._registry = registry or CapabilityRegistry()
        self._required = {
            adapter
            for capability in workspace_manager_profile().required_capabilities
            for adapter in self._registry.adapters_for(capability)
        }
        self._items = self._restore() or self._seed()
        self._reconcile_role_authorities()
        self._persist()

    def list_health(self) -> list[ToolOperationalHealth]:
        return sorted(self._items.values(), key=lambda item: item.adapter_id)

    def get(self, adapter_id: str) -> ToolOperationalHealth:
        try:
            return self._items[adapter_id]
        except KeyError as exc:
            raise GovernanceError(f"unknown tool adapter: {adapter_id}") from exc

    def probe(self, adapter_id: str) -> ToolOperationalHealth:
        item = self.get(adapter_id)
        now = datetime.now(UTC)
        metadata = self._registry.adapter(adapter_id)
        item.connection = HealthFact(
            value=metadata["lifecycle"],
            provenance=ValueProvenance.verified_runtime_probe,
            observed_at=now,
            note="Local adapter registry and service path probed; provider not contacted",
        )
        item.permission = HealthFact(
            value=metadata["permission_status"],
            provenance=ValueProvenance.verified_runtime_probe,
            observed_at=now,
            note="Local policy permission evaluated",
        )
        item.freshness = HealthFact(
            value="fresh",
            provenance=ValueProvenance.verified_runtime_probe,
            observed_at=now,
        )
        self._persist()
        return item

    def alerts(self) -> list[ToolHealthAlert]:
        now = datetime.now(UTC)
        alerts: list[ToolHealthAlert] = []
        for item in self._items.values():
            if item.required and item.authentication.value not in {"SET", "not_applicable"}:
                alerts.append(
                    ToolHealthAlert(
                        alert_id=f"{item.adapter_id}-authentication",
                        adapter_id=item.adapter_id,
                        severity=ToolHealthAlertSeverity.warning,
                        code="AUTHENTICATION_UNVERIFIED",
                        message="لا توجد أدلة حالية تثبت مصادقة الأداة أو المزود.",
                        operator_action="شغّل فحصًا موثقًا للمصادقة دون عرض أي قيمة سرية.",
                        observed_at=now,
                    )
                )
            if item.required and item.freshness.value != "fresh":
                alerts.append(
                    ToolHealthAlert(
                        alert_id=f"{item.adapter_id}-stale",
                        adapter_id=item.adapter_id,
                        severity=ToolHealthAlertSeverity.warning,
                        code="HEALTH_EVIDENCE_STALE_OR_UNAVAILABLE",
                        message="دليل الصحة التشغيلية للأداة قديم أو غير متاح.",
                        operator_action="افحص الأداة وأرفق دليلًا حديثًا غير سري.",
                        observed_at=now,
                    )
                )
        return alerts

    def _seed(self) -> dict[str, ToolOperationalHealth]:
        items: dict[str, ToolOperationalHealth] = {}
        for adapter_id, metadata in self._registry.public_snapshot()["adapters"].items():
            permission = HealthFact(
                value=metadata["permission_status"],
                provenance=ValueProvenance.verified_platform_ui,
                note="Authoritative PalWakf adapter registry",
            )
            items[adapter_id] = ToolOperationalHealth(
                adapter_id=adapter_id,
                display_name=adapter_id.replace("-", " ").title(),
                required=adapter_id in self._required,
                connection=_unknown("No provider connectivity probe recorded"),
                authentication=_unknown("No authenticated provider probe recorded"),
                permission=permission,
                entitlement=_unknown(),
                quota=_unknown(),
                usage=_unknown(),
                cost=_unknown(),
                balance=_unknown(),
                credit_expiry=_unknown(),
                renewal=_unknown(),
                rate_limit=_unknown(),
                freshness=HealthFact(
                    value="unverified",
                    provenance=ValueProvenance.stale,
                ),
                operator_actions=["Run an authenticated adapter probe"],
                evidence=["tool-registry:R2_20260815"],
                role_authorities=self._role_authorities(metadata),
            )

        codex = items["codex"]
        observed = datetime(2026, 7, 31, tzinfo=UTC)
        codex.authentication = HealthFact(
            value="SET",
            provenance=ValueProvenance.verified_runtime_probe,
            observed_at=observed,
            note="Runtime recovery V3 evidence; credential value was not captured",
        )
        codex.quota = HealthFact(
            value="AVAILABLE",
            provenance=ValueProvenance.verified_runtime_probe,
            observed_at=observed,
            note="Governed Agents SDK to Codex runtime request completed",
        )
        codex.freshness = HealthFact(
            value="fresh",
            provenance=ValueProvenance.verified_runtime_probe,
            observed_at=observed,
        )
        codex.evidence.append("RUNTIME_RECOVERY_V3:PASS")
        return items

    @staticmethod
    def _role_authorities(metadata: dict[str, object]) -> dict[str, RoleAuthority]:
        raw = metadata.get("role_authorities", {})
        if not isinstance(raw, dict):
            return {}
        return {str(role): RoleAuthority(str(authority)) for role, authority in raw.items()}

    def _reconcile_role_authorities(self) -> None:
        for adapter_id, item in self._items.items():
            metadata = self._registry.adapter(adapter_id)
            item.role_authorities = self._role_authorities(metadata)

    def _restore(self) -> dict[str, ToolOperationalHealth]:
        values = self._store.load().get("tool_health", {})
        return {key: ToolOperationalHealth.model_validate(value) for key, value in values.items()}

    def _persist(self) -> None:
        state = self._store.load()
        state["tool_health"] = {
            key: value.model_dump(mode="json") for key, value in self._items.items()
        }
        self._store.save(state)
