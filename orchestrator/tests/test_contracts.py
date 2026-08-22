import pytest
from pydantic import ValidationError

from palwakf_orchestrator.contracts import DispatchRequest


def valid_request() -> dict:
    return {
        "task_id": "PALWAKF_TEST_001",
        "prompt": "Inspect the repository and report the project name.",
        "repository": "firasfanon/palwakf_workspace_manager",
        "branch": "agent/workspace-manager-foundation-v1",
        "expected_head": "a312d498",
        "idempotency_key": "palwakf-test-001",
        "transport": "sdk",
        "boundaries": {
            "workspace_write": False,
            "database_write": False,
            "production_mutation": False,
            "secret_access": False,
        },
    }


@pytest.mark.parametrize(
    "boundary",
    ["workspace_write", "database_write", "production_mutation", "secret_access"],
)
def test_rejects_forbidden_boundaries(boundary: str) -> None:
    payload = valid_request()
    payload["boundaries"][boundary] = True

    with pytest.raises(ValidationError):
        DispatchRequest.model_validate(payload)


def test_accepts_governed_read_only_request() -> None:
    request = DispatchRequest.model_validate(valid_request())

    assert request.expected_head == "a312d498"
    assert request.boundaries.workspace_write is False
