from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from agents import Agent, Runner

from palwakf_orchestrator.direct_execution_contracts import (
    DirectExecutionReceipt,
    DirectExecutionRequest,
    DirectExecutionStatus,
    DirectWorkspaceClass,
)
from palwakf_orchestrator.persistence import StateStore

DIRECT_EXECUTION_SESSIONS_KEY = "direct_execution_sessions_v1"


class DirectExecutionError(RuntimeError):
    pass


class DirectTextExecutor(Protocol):
    provider_id: str

    async def run(self, *, prompt: str, instructions: str) -> str: ...


class OpenAIAgentsDirectTextExecutor:
    provider_id = "openai-agents-direct"

    def __init__(self, model: str) -> None:
        self.model = model

    async def run(self, *, prompt: str, instructions: str) -> str:
        agent: Any = Agent(
            name="Workspace Direct Executor",
            instructions=instructions,
            model=self.model,
            tools=[],
        )
        result: Any = await Runner.run(agent, input=prompt, max_turns=1)
        output = str(result.final_output or "").strip()
        if not output:
            raise DirectExecutionError("DIRECT_EXECUTION_EMPTY_RESULT")
        return output


class DirectExecutionService:
    """Direct, text-only execution for Research and Private Project workspace classes.

    This service intentionally does not import or invoke EngineeringTask, OperatorService,
    authorization, tool planning, or governed dispatch. It has no filesystem or Git tools.
    """

    def __init__(
        self,
        state_store: StateStore,
        *,
        model: str,
        executor: DirectTextExecutor | None,
    ) -> None:
        self.state_store = state_store
        self.model = model
        self.executor = executor

    async def execute(self, command: DirectExecutionRequest) -> DirectExecutionReceipt:
        self._validate_identity(command)
        started_at = datetime.now(UTC)
        session_id = str(uuid4())
        prompt_sha256 = hashlib.sha256(command.prompt.encode("utf-8")).hexdigest()

        if self.executor is None:
            receipt = DirectExecutionReceipt(
                session_id=session_id,
                item_id=command.item_id,
                item_class=command.item_class,
                project_uid=command.project_uid,
                technical_id=command.technical_id,
                title=command.title,
                status=DirectExecutionStatus.failed,
                provider_id=None,
                model=self.model,
                prompt_sha256=prompt_sha256,
                error_code="DIRECT_EXECUTION_PROVIDER_UNAVAILABLE",
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
            self._save(receipt)
            return receipt

        try:
            output = await self.executor.run(
                prompt=self._compose_prompt(command),
                instructions=self._instructions(command),
            )
            receipt = DirectExecutionReceipt(
                session_id=session_id,
                item_id=command.item_id,
                item_class=command.item_class,
                project_uid=command.project_uid,
                technical_id=command.technical_id,
                title=command.title,
                status=DirectExecutionStatus.completed,
                provider_id=self.executor.provider_id,
                model=self.model,
                prompt_sha256=prompt_sha256,
                output=output,
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )
        except Exception as exc:
            code = str(exc).strip() or exc.__class__.__name__
            receipt = DirectExecutionReceipt(
                session_id=session_id,
                item_id=command.item_id,
                item_class=command.item_class,
                project_uid=command.project_uid,
                technical_id=command.technical_id,
                title=command.title,
                status=DirectExecutionStatus.failed,
                provider_id=self.executor.provider_id,
                model=self.model,
                prompt_sha256=prompt_sha256,
                error_code=f"DIRECT_EXECUTION_FAILED:{code}"[:500],
                started_at=started_at,
                completed_at=datetime.now(UTC),
            )

        self._save(receipt)
        return receipt

    def get(self, session_id: str) -> DirectExecutionReceipt:
        state = self.state_store.load()
        sessions = state.get(DIRECT_EXECUTION_SESSIONS_KEY, {})
        if not isinstance(sessions, dict):
            raise DirectExecutionError("DIRECT_EXECUTION_STATE_CORRUPT")
        value = sessions.get(session_id)
        if not isinstance(value, dict):
            raise DirectExecutionError("DIRECT_EXECUTION_SESSION_NOT_FOUND")
        return DirectExecutionReceipt.model_validate(value)

    @staticmethod
    def _validate_identity(command: DirectExecutionRequest) -> None:
        if command.item_class == DirectWorkspaceClass.palwakf_governed_project:
            raise DirectExecutionError("DIRECT_EXECUTION_REJECTS_PALWAKF_GOVERNED_CLASS")

        if command.item_class == DirectWorkspaceClass.research:
            if not command.item_id.startswith("research:"):
                raise DirectExecutionError("RESEARCH_ITEM_IDENTITY_MISMATCH")
            if command.project_uid is not None:
                raise DirectExecutionError("RESEARCH_MUST_NOT_HAVE_PROJECT_UID")
            return

        if command.item_class == DirectWorkspaceClass.private_project:
            if command.project_uid is None:
                raise DirectExecutionError("PRIVATE_PROJECT_UID_REQUIRED")
            try:
                parsed = UUID(command.project_uid)
            except ValueError as exc:
                raise DirectExecutionError("PRIVATE_PROJECT_UID_INVALID") from exc
            if parsed.version != 4 or str(parsed).lower() != command.project_uid.lower():
                raise DirectExecutionError("PRIVATE_PROJECT_UID_MUST_BE_UUID_V4")
            if command.item_id.lower() != f"private:{command.project_uid}".lower():
                raise DirectExecutionError("PRIVATE_PROJECT_ITEM_UID_MISMATCH")
            if not (command.technical_id or "").strip():
                raise DirectExecutionError("PRIVATE_PROJECT_TECHNICAL_ID_REQUIRED")
            return

        raise DirectExecutionError("DIRECT_EXECUTION_CLASS_UNSUPPORTED")

    @staticmethod
    def _compose_prompt(command: DirectExecutionRequest) -> str:
        context = command.context_summary.strip()
        context_block = f"\n\nسياق العنصر المسجل:\n{context}" if context else ""
        return (
            f"العنصر: {command.title}\n"
            f"المعرف الداخلي: {command.item_id}\n"
            f"الفئة: {command.item_class.value}"
            f"{context_block}\n\n"
            f"طلب المستخدم:\n{command.prompt.strip()}"
        )

    @staticmethod
    def _instructions(command: DirectExecutionRequest) -> str:
        class_rule = (
            "أنت تعمل داخل بحث مسجل. نفّذ الطلب تحليليًا داخل سياق هذا البحث فقط."
            if command.item_class == DirectWorkspaceClass.research
            else (
                "أنت تعمل داخل مشروع خاص معزول بالمعرف الفريد "
                f"{command.project_uid}. نفّذ الطلب داخل هذا المشروع فقط."
            )
        )
        return (
            f"{class_rule}\n"
            "هذا مسار تنفيذ مباشر مستقل عن حوكمة PalWakf. "
            "لا تنشئ Engineering Task ولا Operator Task ولا Tool Plan. "
            "لا تدّع تعديل ملفات أو Git أو قواعد بيانات أو خدمات خارجية؛ "
            "هذا الإصدار من المسار المباشر نصّي ولا يملك أدوات mutation. "
            "قدّم نتيجة عملية واضحة ومباشرة، وميّز بوضوح ما لا يمكن إثباته من السياق المتاح."
        )

    def _save(self, receipt: DirectExecutionReceipt) -> None:
        state = self.state_store.load()
        sessions = state.get(DIRECT_EXECUTION_SESSIONS_KEY, {})
        if not isinstance(sessions, dict):
            sessions = {}
        sessions = dict(sessions)
        sessions[receipt.session_id] = receipt.model_dump(mode="json")
        state[DIRECT_EXECUTION_SESSIONS_KEY] = sessions
        self.state_store.save(state)
