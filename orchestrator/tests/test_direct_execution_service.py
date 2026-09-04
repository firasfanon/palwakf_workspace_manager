from __future__ import annotations

from dataclasses import dataclass

import pytest

from palwakf_orchestrator.direct_execution_contracts import (
    DirectExecutionRequest,
    DirectExecutionStatus,
    DirectWorkspaceClass,
)
from palwakf_orchestrator.direct_execution_service import (
    DirectExecutionError,
    DirectExecutionService,
)
from palwakf_orchestrator.persistence import MemoryStateStore


@dataclass
class FakeExecutor:
    provider_id: str = "fake-direct"
    output: str = "DIRECT_OK"
    failure: str | None = None
    calls: int = 0
    last_prompt: str = ""
    last_instructions: str = ""

    async def run(self, *, prompt: str, instructions: str) -> str:
        self.calls += 1
        self.last_prompt = prompt
        self.last_instructions = instructions
        if self.failure:
            raise RuntimeError(self.failure)
        return self.output


def research_request() -> DirectExecutionRequest:
    return DirectExecutionRequest(
        item_id="research:PAL-EYES-CENSUS-009",
        item_class=DirectWorkspaceClass.research,
        title="كنيسة القيامة",
        prompt="لخّص نقطة الاستئناف الحالية.",
        context_summary="بحث مسجل في Workspace.",
    )


@pytest.mark.asyncio
async def test_research_executes_directly_without_palwakf_governance() -> None:
    store = MemoryStateStore()
    executor = FakeExecutor()
    service = DirectExecutionService(store, model="test-model", executor=executor)

    receipt = await service.execute(research_request())

    assert receipt.status == DirectExecutionStatus.completed
    assert receipt.output == "DIRECT_OK"
    assert receipt.item_id == "research:PAL-EYES-CENSUS-009"
    assert receipt.palwakf_governance_used is False
    assert receipt.engineering_task_used is False
    assert receipt.operator_authorization_used is False
    assert receipt.tool_plan_used is False
    assert executor.calls == 1
    assert "كنيسة القيامة" in executor.last_prompt
    assert "Engineering Task" in executor.last_instructions
    assert service.get(receipt.session_id) == receipt


@pytest.mark.asyncio
async def test_private_project_is_bound_to_immutable_project_uid() -> None:
    uid = "56aa02ac-7f7f-40f5-ba59-02cfed407d6a"
    executor = FakeExecutor()
    service = DirectExecutionService(MemoryStateStore(), model="test-model", executor=executor)
    command = DirectExecutionRequest(
        item_id=f"private:{uid}",
        item_class=DirectWorkspaceClass.private_project,
        project_uid=uid,
        technical_id="SLEEPQUALITY_APP",
        title="جودة النوم",
        prompt="اقترح أول مهمة عملية.",
    )

    receipt = await service.execute(command)

    assert receipt.status == DirectExecutionStatus.completed
    assert receipt.project_uid == uid
    assert receipt.technical_id == "SLEEPQUALITY_APP"
    assert uid in executor.last_instructions


@pytest.mark.asyncio
async def test_governed_project_is_rejected_before_direct_executor() -> None:
    executor = FakeExecutor()
    service = DirectExecutionService(MemoryStateStore(), model="test-model", executor=executor)
    command = DirectExecutionRequest(
        item_id="project:PALWAKF_WORKSPACE_MANAGER",
        item_class=DirectWorkspaceClass.palwakf_governed_project,
        technical_id="PALWAKF_WORKSPACE_MANAGER",
        title="PalWakf Workspace Manager",
        prompt="نفّذ العمل",
    )

    with pytest.raises(
        DirectExecutionError,
        match="DIRECT_EXECUTION_REJECTS_PALWAKF_GOVERNED_CLASS",
    ):
        await service.execute(command)
    assert executor.calls == 0


@pytest.mark.asyncio
async def test_unavailable_provider_fails_closed_with_receipt() -> None:
    service = DirectExecutionService(MemoryStateStore(), model="test-model", executor=None)

    receipt = await service.execute(research_request())

    assert receipt.status == DirectExecutionStatus.failed
    assert receipt.error_code == "DIRECT_EXECUTION_PROVIDER_UNAVAILABLE"
    assert receipt.output == ""
    assert service.get(receipt.session_id) == receipt


@pytest.mark.asyncio
async def test_failure_isolated_to_its_own_direct_session() -> None:
    store = MemoryStateStore()
    failing = FakeExecutor(failure="provider down")
    service = DirectExecutionService(store, model="test-model", executor=failing)

    failed = await service.execute(research_request())
    assert failed.status == DirectExecutionStatus.failed

    healthy = FakeExecutor(output="RECOVERED")
    recovered_service = DirectExecutionService(store, model="test-model", executor=healthy)
    recovered = await recovered_service.execute(research_request())

    assert recovered.status == DirectExecutionStatus.completed
    assert recovered.output == "RECOVERED"
    assert recovered.session_id != failed.session_id
    assert recovered_service.get(failed.session_id).status == DirectExecutionStatus.failed
