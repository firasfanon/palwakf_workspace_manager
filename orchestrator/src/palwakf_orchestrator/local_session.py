from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request

from palwakf_orchestrator.connected_contracts import ClientPrincipal, ServiceScope

LOCAL_SESSION_COOKIE = "palwakf_local_session"


@dataclass(frozen=True)
class _PendingLaunch:
    principal: ClientPrincipal
    expires_at: float


@dataclass(frozen=True)
class _ActiveSession:
    principal: ClientPrincipal
    expires_at: float


class LocalSessionManager:
    """Issues one-time loopback launch links and HttpOnly local sessions."""

    def __init__(
        self,
        *,
        launch_ttl_seconds: int = 60,
        session_ttl_seconds: int = 28_800,
    ) -> None:
        self._launch_ttl_seconds = launch_ttl_seconds
        self._session_ttl_seconds = session_ttl_seconds
        self._pending: dict[str, _PendingLaunch] = {}
        self._sessions: dict[str, _ActiveSession] = {}

    def issue_launch(self, principal: ClientPrincipal) -> str:
        self._purge()
        nonce = secrets.token_urlsafe(32)
        digest = self._digest(nonce)
        self._pending[digest] = _PendingLaunch(
            principal=principal,
            expires_at=time.monotonic() + self._launch_ttl_seconds,
        )
        return nonce

    def redeem_launch(self, nonce: str, request: Request) -> str:
        self._require_loopback(request)
        self._purge()
        digest = self._digest(nonce)
        pending = self._pending.pop(digest, None)
        if pending is None or pending.expires_at <= time.monotonic():
            raise HTTPException(
                status_code=401, detail="local launch session is invalid or expired"
            )
        session_id = secrets.token_urlsafe(32)
        self._sessions[self._digest(session_id)] = _ActiveSession(
            principal=pending.principal,
            expires_at=time.monotonic() + self._session_ttl_seconds,
        )
        return session_id

    def require(
        self,
        request: Request,
        scope: ServiceScope,
    ) -> ClientPrincipal | None:
        self._purge()
        session_id = request.cookies.get(LOCAL_SESSION_COOKIE)
        if not session_id:
            return None
        session = self._sessions.get(self._digest(session_id))
        if session is None or session.expires_at <= time.monotonic():
            return None
        if scope not in session.principal.scopes:
            raise HTTPException(status_code=403, detail=f"missing scope: {scope.value}")
        return session.principal

    def _purge(self) -> None:
        now = time.monotonic()
        self._pending = {
            key: value for key, value in self._pending.items() if value.expires_at > now
        }
        self._sessions = {
            key: value for key, value in self._sessions.items() if value.expires_at > now
        }

    @staticmethod
    def _digest(value: str) -> str:
        return hashlib.sha256(value.encode()).hexdigest()

    @staticmethod
    def _require_loopback(request: Request) -> None:
        host = request.client.host if request.client else ""
        if not any(
            hmac.compare_digest(host, value) for value in ("127.0.0.1", "::1", "testclient")
        ):
            raise HTTPException(
                status_code=403, detail="local session redemption requires loopback"
            )
