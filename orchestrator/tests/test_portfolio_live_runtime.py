from __future__ import annotations

import httpx
import pytest

from palwakf_orchestrator.portfolio_live_runtime import (
    PortfolioLiveRuntimeAdapter,
)


def _response_for(url: str) -> httpx.Response:
    request = httpx.Request("GET", url)

    if url.endswith(":8431/health"):
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "ok",
                "mutation_mode": "READ_ONLY",
            },
        )

    if url.endswith(":8431/ready"):
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "ready",
            },
        )

    if url.endswith(":8431/v1/skills"):
        return httpx.Response(
            200,
            request=request,
            json=[
                {
                    "skill_id": "LEGAL_EVIDENCE",
                    "status": "ACTIVE",
                    "level": "GLOBAL",
                    "owner_scope":
                        "PALWAKF_MIND_ASSISTANT",
                    "provenance_ref":
                        "mind://skills/legal",
                }
            ],
        )

    if url.endswith(
        ":8431/v1/capabilities"
    ):
        return httpx.Response(
            200,
            request=request,
            json=[
                {
                    "capability_id":
                        "knowledge.read",
                    "name":
                        "Knowledge Read",
                    "risk_class": "low",
                    "mutation_class":
                        "read-only",
                    "source_mode":
                        "FIXTURE_DERIVED",
                }
            ],
        )

    if url.endswith(
        ":8431/v1/system/connector"
    ):
        return httpx.Response(
            200,
            request=request,
            json={
                "state": "READY",
                "mode": "FIXTURE_DERIVED",
                "writes_enabled": False,
            },
        )

    if url.endswith(":8015/health"):
        return httpx.Response(
            200,
            request=request,
            json={
                "service":
                    "palwakf-local-agents",
                "platform_mutation_enabled":
                    False,
                "database_access_enabled":
                    False,
                "safety_ok": True,
            },
        )

    if url.endswith(":8015/api/agents"):
        return httpx.Response(
            200,
            request=request,
            json=[
                {
                    "id": "planner",
                    "name_ar": "المخطط",
                    "lifecycle": "AVAILABLE",
                    "authority": "READ_ONLY",
                }
            ],
        )

    raise AssertionError(
        f"unexpected URL {url}"
    )


def test_live_runtime_projects_real_states_without_fabricating_drive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        lambda url, timeout: _response_for(url),
    )

    adapter = PortfolioLiveRuntimeAdapter(
        mind_base_url=
            "http://127.0.0.1:8431",
        agentic_base_url=
            "http://127.0.0.1:8015",
    )

    result = adapter.snapshot()

    sources = {
        item.source_id: item
        for item in result.source_health
    }

    assert (
        sources["MIND_RUNTIME"].state.value
        == "HEALTHY"
    )

    assert (
        sources["AGENTIC_RUNTIME"].state.value
        == "HEALTHY"
    )

    assert (
        sources[
            "WORKSPACE_DRIVE_SOVEREIGN"
        ].state.value
        == "DEGRADED"
    )

    assert (
        "FIXTURE_DERIVED"
        in sources[
            "WORKSPACE_DRIVE_SOVEREIGN"
        ].freshness
    )

    assert len(result.skills) == 1
    assert len(result.capabilities) == 1
    assert len(result.agents) == 1


def test_live_runtime_preserves_last_verified_cache_as_degraded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    online = {"value": True}

    def fake_get(url: str, timeout: float):
        if not online["value"]:
            request = httpx.Request(
                "GET",
                url,
            )
            raise httpx.ConnectError(
                "simulated outage",
                request=request,
            )

        return _response_for(url)

    monkeypatch.setattr(
        httpx,
        "get",
        fake_get,
    )

    adapter = PortfolioLiveRuntimeAdapter(
        mind_base_url=
            "http://127.0.0.1:8431",
        agentic_base_url=
            "http://127.0.0.1:8015",
    )

    first = adapter.snapshot()

    online["value"] = False

    second = adapter.snapshot()

    first_sources = {
        item.source_id: item
        for item in first.source_health
    }

    second_sources = {
        item.source_id: item
        for item in second.source_health
    }

    assert (
        first_sources[
            "MIND_RUNTIME"
        ].state.value
        == "HEALTHY"
    )

    assert (
        second_sources[
            "MIND_RUNTIME"
        ].state.value
        == "DEGRADED"
    )

    assert (
        second_sources[
            "MIND_RUNTIME"
        ].freshness
        == "LAST_VERIFIED_CACHE"
    )
