from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from socket import gethostname

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from palwakf_orchestrator.connected_contracts import ServiceMode


def default_workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PALWAKF_",
        extra="ignore",
        case_sensitive=False,
    )

    workspace_root: Path = Field(default_factory=default_workspace_root)
    repository: str = "firasfanon/palwakf_workspace_manager"
    governed_branch: str = "agent/workspace-manager-foundation-v1"
    openai_model: str = "gpt-5.6-sol"
    codex_model: str | None = None
    bind_host: str = "127.0.0.1"
    port: int = Field(default=8421, ge=1, le=65535)
    agent_max_turns: int = Field(default=1, ge=1, le=3)
    service_mode: ServiceMode = ServiceMode.local_secure
    state_db_path: Path | None = None
    auth_clients_json: str = ""
    execution_host_id: str = Field(default_factory=lambda: f"host-{gethostname().lower()}")
    tool_executor_id: str = "codex-sdk-local"
    queue_capacity: int = Field(default=16, ge=1, le=256)
    worker_count: int = Field(default=2, ge=1, le=16)
    requests_per_minute: int = Field(default=60, ge=1, le=10_000)
    stale_task_seconds: int = Field(default=3_600, ge=60, le=86_400)
    stale_project_seconds: int = Field(default=86_400, ge=300, le=2_592_000)
    public_base_url: str | None = None
    oauth_authorization_server: str | None = None
    oauth_jwks_url: str | None = None
    oauth_audience: str | None = None
    local_project_allowlist_json: str = "[]"

    @property
    def resolved_state_db_path(self) -> Path:
        return self.state_db_path or self.workspace_root / ".palwakf" / "orchestrator.sqlite3"

    def assert_safe_binding(self) -> None:
        loopback = self.bind_host in {"127.0.0.1", "localhost", "::1"}
        if self.service_mode == ServiceMode.local_secure and not loopback:
            raise RuntimeError("LOCAL_SECURE_MODE rejects non-loopback binding")
        if self.service_mode == ServiceMode.remote_or_tunnel:
            if any(
                value is None
                for value in (
                    self.public_base_url,
                    self.oauth_authorization_server,
                    self.oauth_jwks_url,
                    self.oauth_audience,
                )
            ):
                raise RuntimeError(
                    "REMOTE_OR_TUNNEL_MODE requires HTTPS base URL and complete OAuth/JWKS config"
                )
            assert self.public_base_url is not None
            if not self.public_base_url.startswith("https://"):
                raise RuntimeError("REMOTE_OR_TUNNEL_MODE requires HTTPS")

    def assert_local_only(self) -> None:
        self.assert_safe_binding()

    @property
    def local_project_allowlist(self) -> tuple[Path, ...]:
        try:
            values = json.loads(self.local_project_allowlist_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("LOCAL_PROJECT_ALLOWLIST_JSON must be valid JSON") from exc
        if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
            raise RuntimeError("LOCAL_PROJECT_ALLOWLIST_JSON must be a JSON string array")
        return tuple(Path(value).resolve() for value in values)


@lru_cache
def get_settings() -> Settings:
    return Settings()
