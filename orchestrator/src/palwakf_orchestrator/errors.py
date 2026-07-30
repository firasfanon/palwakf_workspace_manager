class OrchestratorError(RuntimeError):
    """Base error for governed dispatch failures."""


class GovernanceError(OrchestratorError):
    """The request or repository state violated a sovereignty gate."""


class GatewayError(OrchestratorError):
    """Codex SDK or MCP execution failed."""
