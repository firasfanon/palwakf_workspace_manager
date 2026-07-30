from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    def assert_local_only(self) -> None:
        if self.bind_host not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError("V1 orchestrator rejects non-loopback binding")


@lru_cache
def get_settings() -> Settings:
    return Settings()
