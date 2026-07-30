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

CODEX_DEVELOPER_INSTRUCTIONS = """
Operate in read-only inspection mode.
Do not edit files, run Git mutations, access secrets, connect to databases,
send external messages, deploy, merge, or promote production.
Return findings and evidence only.
""".strip()


class _CodexEventNoiseFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.getMessage().startswith("Failed to validate notification")


class CodexGateway(Protocol):
    async def run(self, prompt: str, workspace: Path) -> GatewayResult: ...


class CodexSdkGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, prompt: str, workspace: Path) -> GatewayResult:
        config = CodexConfig(cwd=str(workspace))
        async with AsyncCodex(config) as codex:
            thread = await codex.thread_start(
                approval_mode=ApprovalMode.deny_all,
                cwd=str(workspace),
                developer_instructions=CODEX_DEVELOPER_INSTRUCTIONS,
                ephemeral=True,
                model=self._settings.codex_model,
                sandbox=Sandbox.read_only,
            )
            result = await thread.run(
                prompt,
                approval_mode=ApprovalMode.deny_all,
                cwd=str(workspace),
                model=self._settings.codex_model,
                sandbox=Sandbox.read_only,
            )
        final_response = result.final_response or ""
        if not final_response:
            raise GatewayError(f"Codex SDK returned no final response; status={result.status}")
        return GatewayResult(
            transport=Transport.sdk,
            thread_id=thread.id,
            status=str(result.status),
            final_response=final_response,
        )


class CodexMcpGateway:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def run(self, prompt: str, workspace: Path) -> GatewayResult:
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
            await server.connect()
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
            await server.cleanup()
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
