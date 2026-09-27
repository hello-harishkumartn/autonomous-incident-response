"""Central registry — the single place that knows about all 12 tools."""
from __future__ import annotations

from app.tools.base import Tool
from app.tools.diagnostic_and_action_tools import (
    CreateIncidentNoteTool,
    ExecuteDiagnosticTool,
    RestartServiceTool,
    RollbackDeploymentTool,
)
from app.tools.read_tools import (
    GetConfigTool,
    GetDeploymentTool,
    GetGitDiffTool,
    GetTraceTool,
    InspectServiceTool,
    QueryLogsTool,
    QueryMetricsTool,
    RunHealthCheckTool,
)

_TOOLS: list[Tool] = [
    QueryLogsTool(),
    QueryMetricsTool(),
    GetTraceTool(),
    InspectServiceTool(),
    GetDeploymentTool(),
    GetGitDiffTool(),
    GetConfigTool(),
    RunHealthCheckTool(),
    ExecuteDiagnosticTool(),
    RestartServiceTool(),
    RollbackDeploymentTool(),
    CreateIncidentNoteTool(),
]

TOOL_REGISTRY: dict[str, Tool] = {t.name: t for t in _TOOLS}


def get_tool(name: str) -> Tool:
    if name not in TOOL_REGISTRY:
        raise KeyError(f"Unknown tool '{name}'. Known tools: {sorted(TOOL_REGISTRY)}")
    return TOOL_REGISTRY[name]


def list_tool_schemas() -> list[dict]:
    return [t.schema() for t in _TOOLS]


READ_ONLY_TOOLS = {"query_logs", "query_metrics", "get_trace", "inspect_service", "get_deployment", "get_git_diff", "get_config", "run_health_check", "create_incident_note"}
INVESTIGATION_TOOLS = READ_ONLY_TOOLS | {"execute_diagnostic"}
REMEDIATION_TOOLS = {"restart_service", "rollback_deployment"}
