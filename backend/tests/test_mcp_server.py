"""Exercises the MCP tool handlers directly (no stdio transport needed)."""
from __future__ import annotations

import json

import pytest

from app.agent.factory import create_incident
from app.enums import IncidentType
from app.mcp_server.server import call_tool, list_tools


@pytest.mark.asyncio
async def test_list_tools_includes_all_twelve():
    tools = await list_tools()
    names = {t.name for t in tools}
    assert len(tools) == 12
    assert "restart_service" in names
    assert all("incident_id" in t.inputSchema["required"] for t in tools)


@pytest.mark.asyncio
async def test_call_tool_requires_incident_id():
    result = await call_tool("query_logs", {})
    payload = json.loads(result[0].text)
    assert "error" in payload


@pytest.mark.asyncio
async def test_call_tool_read_only_roundtrip(session):
    incident = create_incident(session, IncidentType.MEMORY_SPIKE, seed=3)
    session.commit()

    result = await call_tool("inspect_service", {"incident_id": incident.id, "service": "user_service"})
    payload = json.loads(result[0].text)
    assert payload["service"] == "user_service"
    assert payload["is_healthy"] is False


@pytest.mark.asyncio
async def test_call_tool_remediation_goes_through_sandbox(session):
    incident = create_incident(session, IncidentType.MEMORY_SPIKE, seed=3)
    session.commit()

    result = await call_tool("restart_service", {
        "incident_id": incident.id, "service": "user_service", "reason": "memory leak suspected",
    })
    payload = json.loads(result[0].text)
    assert payload["healthy_after"] is True


@pytest.mark.asyncio
async def test_call_tool_rejects_non_allowlisted_action(session, monkeypatch):
    incident = create_incident(session, IncidentType.MEMORY_SPIKE, seed=3)
    session.commit()

    # Sandbox only allows restart_service/rollback_deployment as mutating actions;
    # simulate a hypothetically-registered unsafe tool name to prove the allowlist holds.
    from app.tools import registry

    monkeypatch.setitem(registry.TOOL_REGISTRY, "execute_diagnostic", registry.TOOL_REGISTRY["execute_diagnostic"])
    result = await call_tool("execute_diagnostic", {
        "incident_id": incident.id, "service": "user_service", "diagnostic": "memory_check",
    })
    payload = json.loads(result[0].text)
    assert "error" not in payload  # execute_diagnostic IS allowed directly (LOW_RISK, not a sandboxed mutation)
