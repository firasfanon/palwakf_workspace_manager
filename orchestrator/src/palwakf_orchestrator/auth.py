from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections import defaultdict, deque
from collections.abc import Iterable
from dataclasses import dataclass

import jwt
from fastapi import HTTPException, Request
from fastapi.security.utils import get_authorization_scheme_param
from jwt import PyJWKClient

from palwakf_orchestrator.connected_contracts import ClientPrincipal, ServiceScope


@dataclass(frozen=True)
class ClientCredential:
    client_id: str
    token_sha256: str
    scopes: frozenset[ServiceScope]


@dataclass(frozen=True)
class JwtAuthConfig:
    issuer: str
    audience: str
    jwks_url: str


class AuthRegistry:
    def __init__(
        self,
        credentials: Iterable[ClientCredential] = (),
        *,
        jwt_config: JwtAuthConfig | None = None,
    ) -> None:
        self._credentials = tuple(credentials)
        self._jwt_config = jwt_config
        self._jwks_client = PyJWKClient(jwt_config.jwks_url) if jwt_config else None

    @classmethod
    def from_json(
        cls,
        value: str,
        *,
        jwt_config: JwtAuthConfig | None = None,
    ) -> AuthRegistry:
        parsed = json.loads(value) if value.strip() else []
        return cls(
            (
                ClientCredential(
                    client_id=item["client_id"],
                    token_sha256=item["token_sha256"].lower(),
                    scopes=frozenset(ServiceScope(scope) for scope in item["scopes"]),
                )
                for item in parsed
            ),
            jwt_config=jwt_config,
        )

    @classmethod
    def for_testing(
        cls,
        client_id: str,
        token: str,
        scopes: Iterable[ServiceScope] = tuple(ServiceScope),
    ) -> AuthRegistry:
        return cls(
            [
                ClientCredential(
                    client_id=client_id,
                    token_sha256=hashlib.sha256(token.encode()).hexdigest(),
                    scopes=frozenset(scopes),
                )
            ]
        )

    @property
    def configured(self) -> bool:
        return bool(self._credentials or self._jwt_config)

    def authenticate(self, token: str) -> ClientPrincipal | None:
        digest = hashlib.sha256(token.encode()).hexdigest()
        for credential in self._credentials:
            if hmac.compare_digest(digest, credential.token_sha256):
                return ClientPrincipal(
                    client_id=credential.client_id,
                    scopes=credential.scopes,
                )
        if self._jwt_config and self._jwks_client:
            try:
                signing_key = self._jwks_client.get_signing_key_from_jwt(token)
                claims = jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=["RS256", "ES256"],
                    audience=self._jwt_config.audience,
                    issuer=self._jwt_config.issuer,
                    options={"require": ["exp", "iat", "iss", "sub"]},
                )
                raw_scopes = claims.get("scope", "")
                scope_values = (
                    raw_scopes.split() if isinstance(raw_scopes, str) else list(raw_scopes)
                )
                known_scopes = {scope.value for scope in ServiceScope}
                scopes = frozenset(
                    ServiceScope(value) for value in scope_values if value in known_scopes
                )
                client_id = claims.get("client_id") or claims["sub"]
                return ClientPrincipal(client_id=str(client_id), scopes=scopes)
            except (jwt.PyJWTError, ValueError, KeyError):
                return None
        return None

    def require(self, request: Request, scope: ServiceScope) -> ClientPrincipal:
        scheme, token = get_authorization_scheme_param(request.headers.get("Authorization"))
        principal = self.authenticate(token) if scheme.lower() == "bearer" else None
        if principal is None:
            raise HTTPException(
                status_code=401,
                detail="valid bearer authentication is required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if scope not in principal.scopes:
            raise HTTPException(status_code=403, detail=f"missing scope: {scope.value}")
        return principal


class BoundedRateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self._limit = requests_per_minute
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    def require(self, client_id: str) -> None:
        now = time.monotonic()
        bucket = self._requests[client_id]
        while bucket and bucket[0] <= now - 60:
            bucket.popleft()
        if len(bucket) >= self._limit:
            raise HTTPException(status_code=429, detail="client rate limit exceeded")
        bucket.append(now)
