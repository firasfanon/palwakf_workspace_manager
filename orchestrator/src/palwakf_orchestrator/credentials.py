from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Literal

from palwakf_orchestrator.errors import GatewayError

KEY_NAME = "OPENAI_API_KEY"
SOURCE_NAME = "PALWAKF_OPENAI_API_KEY_SOURCE"


@dataclass(frozen=True)
class CredentialPresence:
    state: Literal["SET", "NOT_SET"]
    source_class: str

    def as_safe_dict(self) -> dict[str, str]:
        return asdict(self)


def probe_openai_api_key() -> CredentialPresence:
    is_set = bool(os.environ.get(KEY_NAME, "").strip())
    if not is_set:
        return CredentialPresence(state="NOT_SET", source_class="none")

    source = os.environ.get(SOURCE_NAME, "process").strip() or "process"
    return CredentialPresence(state="SET", source_class=source)


def require_openai_api_key() -> CredentialPresence:
    presence = probe_openai_api_key()
    if presence.state != "SET":
        raise GatewayError("OPENAI_API_KEY is unavailable to the orchestrator runtime")
    return presence
