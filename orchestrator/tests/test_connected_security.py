import logging

import pytest

from palwakf_orchestrator.auth import AuthRegistry
from palwakf_orchestrator.config import Settings
from palwakf_orchestrator.connected_contracts import ServiceMode, ServiceScope
from palwakf_orchestrator.safe_logging import RedactingFilter


def test_remote_mode_requires_complete_https_oauth_configuration() -> None:
    with pytest.raises(RuntimeError, match="complete OAuth"):
        Settings(
            service_mode=ServiceMode.remote_or_tunnel,
            bind_host="0.0.0.0",
            public_base_url="https://orchestrator.example",
            oauth_authorization_server="https://auth.example",
        ).assert_safe_binding()

    with pytest.raises(RuntimeError, match="requires HTTPS"):
        Settings(
            service_mode=ServiceMode.remote_or_tunnel,
            bind_host="0.0.0.0",
            public_base_url="http://orchestrator.example",
            oauth_authorization_server="https://auth.example",
            oauth_jwks_url="https://auth.example/.well-known/jwks.json",
            oauth_audience="https://orchestrator.example/mcp",
        ).assert_safe_binding()


def test_static_bearer_auth_separates_identity_and_scope() -> None:
    registry = AuthRegistry.for_testing(
        "read-client",
        "ephemeral-test-token",
        scopes=(ServiceScope.read,),
    )

    principal = registry.authenticate("ephemeral-test-token")

    assert principal is not None
    assert principal.client_id == "read-client"
    assert principal.scopes == frozenset({ServiceScope.read})
    assert registry.authenticate("wrong-token") is None


def test_log_filter_redacts_bearers_and_api_keys() -> None:
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authorization=Bearer private-value api_key=private-value",
        args=(),
        exc_info=None,
    )

    RedactingFilter().filter(record)

    assert "private-value" not in record.getMessage()
    assert record.getMessage().count("[REDACTED]") == 2
