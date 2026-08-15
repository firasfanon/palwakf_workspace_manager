from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from palwakf_orchestrator.errors import GovernanceError
from palwakf_orchestrator.operator_contracts import (
    AdapterExclusion,
    PermissionStatus,
    ProjectCapabilityProfile,
    TaskCapabilityRequest,
    ToolPlanResponse,
    ToolSelectionDecision,
)


def default_registry_path() -> Path:
    return (
        Path(__file__).resolve().parents[2]
        / "data"
        / "PALWAKF_TOOL_ROLE_AND_INVOCATION_REGISTRY_R2_20260815.json"
    )


class CapabilityRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or default_registry_path()
        self._snapshot = json.loads(self._path.read_text(encoding="utf-8"))

    @property
    def version(self) -> str:
        return str(self._snapshot["registry_version"])

    def public_snapshot(self) -> dict[str, Any]:
        return deepcopy(self._snapshot)

    def adapters_for(self, capability_id: str) -> list[str]:
        return list(self._snapshot["capabilities"].get(capability_id, []))

    def adapter(self, adapter_id: str) -> dict[str, Any]:
        return dict(self._snapshot["adapters"][adapter_id])


def workspace_manager_profile() -> ProjectCapabilityProfile:
    return ProjectCapabilityProfile(
        project_id="PALWAKF_WORKSPACE_MANAGER",
        project_type="flutter-python-control-plane",
        domain_tags=["engineering-operations", "governance", "self-hosting"],
        stack=["Flutter", "Python", "FastAPI", "GitHub Actions", "Vercel"],
        required_capabilities=[
            "governed.patch_relay",
            "source.control",
            "continuous.integration",
            "runtime.verification",
            "evidence.capture",
        ],
        conditional_capabilities=[
            "product.design",
            "legal.authority",
            "academic.discovery",
            "academic.fulltext",
            "ml.hub",
            "communication.asset",
            "relational.runtime",
        ],
        prohibited_capabilities=["relational.runtime"],
        preferred_adapters={
            "governed.patch_relay": ["codex"],
            "source.control": ["github"],
            "continuous.integration": ["github-actions"],
            "runtime.verification": ["local-runtime"],
            "evidence.capture": ["evidence-recorder"],
            "product.design": ["figma"],
            "communication.asset": ["canva"],
            "legal.authority": ["midpage"],
            "academic.discovery": ["consensus"],
            "academic.fulltext": ["scispace"],
            "ml.hub": ["hugging-face"],
        },
        fallback_adapters={"legal.authority": ["official-source"]},
        environment_boundaries=[
            "NO_DATABASE_WRITE",
            "NO_PRODUCTION_MUTATION",
            "LOCAL_OR_PREVIEW_ONLY",
        ],
        approval_classes=["SOURCE_WRITE", "EXTERNAL_WRITE", "MODEL_UPLOAD"],
        evidence_requirements=[
            "thread_or_relay_reference",
            "commit_sha",
            "test_results",
            "ci_result",
            "manifest_sha256",
        ],
        profile_source="docs/governance/PLATFORM_GUIDE_PIN.md",
        profile_version="1.1.0",
    )


class CapabilityRouter:
    def __init__(self, registry: CapabilityRegistry | None = None) -> None:
        self.registry = registry or CapabilityRegistry()

    def plan(
        self,
        request: TaskCapabilityRequest,
        profile: ProjectCapabilityProfile,
    ) -> ToolPlanResponse:
        if request.project_id != profile.project_id:
            raise GovernanceError("task project does not match capability profile")
        required_ids = list(
            dict.fromkeys([*profile.required_capabilities, *request.required_capability_ids])
        )
        capability_ids = list(dict.fromkeys([*required_ids, *request.optional_capability_ids]))
        decisions = [
            self._select(
                capability_id,
                required=capability_id in required_ids,
                request=request,
                profile=profile,
                invocation_order=index + 1,
            )
            for index, capability_id in enumerate(capability_ids)
        ]
        for capability_id in profile.conditional_capabilities:
            if capability_id not in capability_ids:
                decisions.append(
                    self._excluded_not_requested(
                        capability_id,
                        profile,
                        len(decisions) + 1,
                    )
                )
        blockers = [
            f"NO_USABLE_ADAPTER:{decision.capability_id}"
            for decision in decisions
            if decision.blocked and decision.capability_id in required_ids
        ]
        return ToolPlanResponse(
            task_id=request.task_id,
            project_id=request.project_id,
            decisions=decisions,
            dispatch_blocked=bool(blockers),
            blockers=blockers,
        )

    def _select(
        self,
        capability_id: str,
        *,
        required: bool,
        request: TaskCapabilityRequest,
        profile: ProjectCapabilityProfile,
        invocation_order: int,
    ) -> ToolSelectionDecision:
        candidates = self.registry.adapters_for(capability_id)
        if not candidates:
            return self._blocked_decision(
                capability_id,
                "capability is absent from the authoritative registry",
                invocation_order,
            )
        if capability_id in profile.prohibited_capabilities:
            return ToolSelectionDecision(
                capability_id=capability_id,
                selected_adapter_id=None,
                fallback_adapter_id=None,
                selected_reason="project profile prohibits this capability",
                excluded_adapters_with_reason=[
                    AdapterExclusion(
                        adapter_id=adapter,
                        reason="prohibited by project capability profile",
                    )
                    for adapter in candidates
                ],
                permission_status=PermissionStatus.blocked,
                approval_required=False,
                invocation_order=invocation_order,
                evidence_contract=[],
                decision_timestamp=datetime.now(UTC),
                registry_version=self.registry.version,
                blocked=required,
                substituted=False,
            )

        preferred = profile.preferred_adapters.get(capability_id, [])
        fallbacks = profile.fallback_adapters.get(capability_id, [])
        ordered = list(dict.fromkeys([*preferred, *fallbacks, *candidates]))
        exclusions: list[AdapterExclusion] = []
        selected: str | None = None
        selected_metadata: dict[str, Any] = {}
        substituted = False
        for adapter_id in ordered:
            if adapter_id not in candidates:
                exclusions.append(
                    AdapterExclusion(
                        adapter_id=adapter_id,
                        reason="adapter does not implement requested capability",
                    )
                )
                continue
            metadata = self.registry.adapter(adapter_id)
            lifecycle = metadata["lifecycle"]
            permission = metadata["permission_status"]
            if lifecycle != "available":
                exclusions.append(
                    AdapterExclusion(
                        adapter_id=adapter_id,
                        reason=f"adapter lifecycle is {lifecycle}",
                    )
                )
                continue
            if permission in {"blocked", "untested"}:
                exclusions.append(
                    AdapterExclusion(
                        adapter_id=adapter_id,
                        reason=f"adapter permission is {permission}",
                    )
                )
                continue
            selected = adapter_id
            selected_metadata = metadata
            substituted = adapter_id in fallbacks and adapter_id not in preferred
            break

        for adapter_id in candidates:
            if adapter_id != selected and not any(
                exclusion.adapter_id == adapter_id for exclusion in exclusions
            ):
                exclusions.append(
                    AdapterExclusion(
                        adapter_id=adapter_id,
                        reason="not selected because a smaller preferred adapter set is sufficient",
                    )
                )

        if selected is None:
            return ToolSelectionDecision(
                capability_id=capability_id,
                selected_adapter_id=None,
                fallback_adapter_id=fallbacks[0] if fallbacks else None,
                selected_reason="no authorized and available adapter preserves required semantics",
                excluded_adapters_with_reason=exclusions,
                permission_status=PermissionStatus.blocked,
                approval_required=False,
                invocation_order=invocation_order,
                evidence_contract=[],
                decision_timestamp=datetime.now(UTC),
                registry_version=self.registry.version,
                blocked=required,
                substituted=False,
            )

        permission_status = PermissionStatus(selected_metadata["permission_status"])
        write_capable = bool(selected_metadata["write_capable"])
        approval_required = permission_status == PermissionStatus.approval_required or (
            substituted and write_capable
        )
        if (
            request.mutation_class == "read-only"
            and write_capable
            and not selected_metadata["read_only_fallback"]
            and selected != "codex"
        ):
            approval_required = True
        return ToolSelectionDecision(
            capability_id=capability_id,
            selected_adapter_id=selected,
            fallback_adapter_id=fallbacks[0] if fallbacks else None,
            selected_reason=(
                "selected as policy-authorized fallback preserving read-only semantics"
                if substituted
                else "selected as the minimum preferred adapter for this capability"
            ),
            excluded_adapters_with_reason=exclusions,
            permission_status=permission_status,
            approval_required=approval_required,
            invocation_order=invocation_order,
            evidence_contract=list(selected_metadata["evidence_contract"]),
            decision_timestamp=datetime.now(UTC),
            registry_version=self.registry.version,
            blocked=False,
            substituted=substituted,
        )

    def _blocked_decision(
        self,
        capability_id: str,
        reason: str,
        invocation_order: int,
    ) -> ToolSelectionDecision:
        return ToolSelectionDecision(
            capability_id=capability_id,
            selected_adapter_id=None,
            fallback_adapter_id=None,
            selected_reason=reason,
            excluded_adapters_with_reason=[],
            permission_status=PermissionStatus.blocked,
            approval_required=False,
            invocation_order=invocation_order,
            evidence_contract=[],
            decision_timestamp=datetime.now(UTC),
            registry_version=self.registry.version,
            blocked=True,
            substituted=False,
        )

    def _excluded_not_requested(
        self,
        capability_id: str,
        profile: ProjectCapabilityProfile,
        invocation_order: int,
    ) -> ToolSelectionDecision:
        reason = (
            "capability is prohibited by the project profile"
            if capability_id in profile.prohibited_capabilities
            else "capability is not required by this project task"
        )
        return ToolSelectionDecision(
            capability_id=capability_id,
            selected_adapter_id=None,
            fallback_adapter_id=None,
            selected_reason=reason,
            excluded_adapters_with_reason=[
                AdapterExclusion(adapter_id=adapter, reason=reason)
                for adapter in self.registry.adapters_for(capability_id)
            ],
            permission_status=(
                PermissionStatus.blocked
                if capability_id in profile.prohibited_capabilities
                else PermissionStatus.authorized
            ),
            approval_required=False,
            invocation_order=invocation_order,
            evidence_contract=[],
            decision_timestamp=datetime.now(UTC),
            registry_version=self.registry.version,
            blocked=False,
            substituted=False,
        )
