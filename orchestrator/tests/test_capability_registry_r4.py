from palwakf_orchestrator.capability_router import CapabilityRegistry


def test_r4_selects_palwakf_remote_mcp_for_normal_local_execution() -> None:
    registry = CapabilityRegistry()
    assert registry.version == "PALWAKF_TOOL_ROLE_AND_INVOCATION_REGISTRY_R4_20260928"
    assert registry.adapters_for("governed.local_execution_channel") == [
        "palwakf-remote-mcp"
    ]
    for capability in (
        "mesh_device_info",
        "mesh_hostname",
        "file_read",
        "temp_write",
        "temp_delete",
        "bounded_powershell",
        "process_port_readback",
        "git_readback",
        "playwright_screenshot_uat",
        "audit_readback",
    ):
        assert registry.adapters_for(capability) == ["palwakf-remote-mcp"]

    metadata = registry.adapter("palwakf-remote-mcp")
    assert metadata["provider_kind"] == "governed_remote_execution_transport"
    assert metadata["authority_owner"] == "Workspace"
    assert metadata["execution_router"] == "Agentic"
    assert metadata["sovereign_authority"] == "NONE"
    assert metadata["transport_only"] is True
    assert metadata["arbitrary_shell_exposed"] is False
    assert metadata["source_write_authorized"] is False
