from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Protocol

from agents.mcp import MCPServerStdio
from codex_cli_bin import bundled_codex_path
from openai_codex import ApprovalMode, AsyncCodex, CodexConfig, Sandbox

from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.contracts import GatewayResult, Transport
from palwakf_orchestrator.errors import GatewayError
from palwakf_orchestrator.safe_logging import redact

CODEX_DEVELOPER_INSTRUCTIONS = """
Operate as a governed engineering specialist in the provider mode declared by
the task envelope. Read-only modes may inspect code, review diffs, diagnose
complex or repeated faults, run non-mutating checks, analyze regressions, and
produce engineering proposals with trade-offs. Do not edit files or run Git
mutations. Do not access secrets or databases, send external messages, deploy,
merge, or promote production. An engineering proposal may recommend an
architecture or refactor but must never apply it without separate authority.
Return findings, evidence, uncertainty, and escalation needs explicitly.
""".strip()

CODEX_WRITE_DEVELOPER_INSTRUCTIONS = """
Operate only inside the current PalWakf Workspace Manager repository and the
explicit task authority budget. Source mutation is allowed only for
execution_relay or bounded_bug_fix mode. You may perform bounded diagnosis
needed to complete the authorized task, but must not expand scope, change
requirements, redesign architecture, apply an unrequested refactor, add
dependencies outside policy, access secrets or environment values, connect to
databases or Supabase, touch production, mutate another project, merge, or
promote a baseline. If the correct fix requires any action outside the authority
budget, stop and escalate instead of guessing. Run the requested deterministic
checks, but do not stage files, commit, push, reset, checkout, rebase, merge, tag,
or mutate Git refs. Leave only the exact authorized source changes in the
worktree. The sovereign Workspace completion gate verifies scope and performs
the single governed commit and non-force push after you return. Return the
required structured handoff only after every shell call has completed and its
output has been received.
""".strip()

CODEX_WRITE_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "task_id": {"type": "string"},
        "status": {"type": "string", "enum": ["completed"]},
        "before_head": {"type": "string"},
        "changed_files": {"type": "array", "items": {"type": "string"}},
        "tests": {"type": "array", "items": {"type": "string"}},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": [
        "task_id",
        "status",
        "before_head",
        "changed_files",
        "tests",
        "evidence",
        "summary",
    ],
}


class _CodexEventNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.getMessage().startswith("Failed to validate notification")


class ExecutorGateway(Protocol):
    executor_id: str

    async def run(
        self,
        prompt: str,
        workspace: Path,
        *,
        workspace_write: bool = False,
    ) -> GatewayResult: ...


class CodexGateway(ExecutorGateway, Protocol):
    # Compatibility protocol alias for existing Codex-specific callers.
    pass


class CodexSdkGateway:
    executor_id = "codex"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(
        self,
        prompt: str,
        workspace: Path,
        *,
        workspace_write: bool = False,
    ) -> GatewayResult:
        sandbox = Sandbox.workspace_write if workspace_write else Sandbox.read_only
        instructions = (
            CODEX_WRITE_DEVELOPER_INSTRUCTIONS if workspace_write else CODEX_DEVELOPER_INSTRUCTIONS
        )
        config = CodexConfig(cwd=str(workspace))
        async with AsyncCodex(config) as codex:
            thread = await codex.thread_start(
                approval_mode=ApprovalMode.deny_all,
                cwd=str(workspace),
                developer_instructions=instructions,
                ephemeral=False,
                model=self._settings.codex_model,
                sandbox=sandbox,
            )
            result = await thread.run(
                prompt,
                approval_mode=ApprovalMode.deny_all,
                cwd=str(workspace),
                model=self._settings.codex_model,
                output_schema=CODEX_WRITE_RESULT_SCHEMA if workspace_write else None,
                sandbox=sandbox,
            )
        final_response = result.final_response or ""
        if not final_response:
            raise GatewayError(f"Codex SDK returned no final response; status={result.status}")
        return GatewayResult(
            transport=Transport.sdk,
            thread_id=thread.id,
            status=str(result.status),
            final_response=final_response,
            tool_outputs=self._tool_outputs(result.items),
        )

    @staticmethod
    def _tool_outputs(items: list[Any]) -> list[dict[str, object]]:
        outputs: list[dict[str, object]] = []
        for item in items:
            value = getattr(item, "root", item)
            if getattr(value, "type", None) != "commandExecution":
                continue
            outputs.append(
                {
                    "tool_call_id": str(getattr(value, "id", "")),
                    "command_summary": redact(getattr(value, "command", ""))[:500],
                    "output_excerpt": redact(getattr(value, "aggregated_output", "") or "")[:2_000],
                    "exit_code": getattr(value, "exit_code", None),
                }
            )
        return outputs


class CodexMcpGateway:
    executor_id = "codex"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(
        self,
        prompt: str,
        workspace: Path,
        *,
        workspace_write: bool = False,
    ) -> GatewayResult:
        if workspace_write:
            raise GatewayError("Codex MCP workspace-write dispatch is not enabled")
        server = MCPServerStdio(
            params={
                "command": str(bundled_codex_path()),
                "args": ["mcp-server"],
                "cwd": workspace,
            },
            name="Codex MCP",
            client_session_timeout_seconds=360,
            use_structured_content=True,
        )
        noise_filter = _CodexEventNoiseFilter()
        root_logger = logging.getLogger()
        root_logger.addFilter(noise_filter)
        try:
            await server.connect()  # type: ignore[no-untyped-call]
            arguments: dict[str, Any] = {
                "prompt": prompt,
                "approval-policy": "never",
                "cwd": str(workspace),
                "developer-instructions": CODEX_DEVELOPER_INSTRUCTIONS,
                "sandbox": "read-only",
            }
            if self._settings.codex_model:
                arguments["model"] = self._settings.codex_model
            result = await server.call_tool("codex", arguments)
        finally:
            await server.cleanup()  # type: ignore[no-untyped-call]
            root_logger.removeFilter(noise_filter)

        if getattr(result, "isError", False) or getattr(result, "is_error", False):
            raise GatewayError(f"Codex MCP failed: {self._content_text(result)}")

        structured = getattr(result, "structuredContent", None) or getattr(
            result, "structured_content", None
        )
        structured = structured if isinstance(structured, dict) else {}
        final_response = str(structured.get("content") or self._content_text(result))
        if not final_response:
            raise GatewayError("Codex MCP returned no final response")
        return GatewayResult(
            transport=Transport.mcp,
            thread_id=structured.get("threadId"),
            status="completed",
            final_response=final_response,
        )

    @staticmethod
    def _content_text(result: Any) -> str:
        parts = []
        for block in getattr(result, "content", []):
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "\n".join(parts)
