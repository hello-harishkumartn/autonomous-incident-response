"""MCP-compatible tool server — the same 12 tools, over the Model Context
Protocol, so any MCP client (Claude Desktop, another agent framework, etc.)
can drive an incident investigation instead of only the built-in agent loop.

Every call is scoped to one incident run via a required `incident_id`
argument (there is no global/shared world — each incident is its own
isolated, reproducible fleet snapshot), and remediation tools are still
routed through `SandboxExecutor`, so the allowlist guarantee holds
regardless of which caller — the built-in loop or an external MCP client —
is driving.

Run standalone with:  python -m app.mcp_server.server
"""
from __future__ import annotations

import asyncio
import json
import logging

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from app import models_db as m
from app.db import SessionLocal
from app.safety.sandbox import SandboxExecutor, SandboxViolation
from app.simulator.engine import SimulationEngine
from app.simulator.scenarios import get_scenario
from app.tools.base import ToolContext
from app.tools.registry import REMEDIATION_TOOLS, TOOL_REGISTRY, get_tool

logger = logging.getLogger(__name__)
server = Server("aire-tools")


def _merged_schema(tool) -> dict:
    schema = dict(tool.args_model.model_json_schema())
    properties = dict(schema.get("properties", {}))
    properties["incident_id"] = {"type": "string", "description": "Which incident run to operate on."}
    schema["properties"] = properties
    required = list(schema.get("required", []))
    if "incident_id" not in required:
        required.append("incident_id")
    schema["required"] = required
    return schema


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(name=tool.name, description=tool.description, inputSchema=_merged_schema(tool))
        for tool in TOOL_REGISTRY.values()
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    arguments = dict(arguments or {})
    incident_id = arguments.pop("incident_id", None)
    if not incident_id:
        return [_error("Missing required argument 'incident_id'.")]

    try:
        tool = get_tool(name)
    except KeyError as exc:
        return [_error(str(exc))]

    session = SessionLocal()
    try:
        incident = session.get(m.Incident, incident_id)
        if incident is None:
            return [_error(f"Unknown incident_id '{incident_id}'.")]

        scenario = get_scenario(incident.scenario_type)
        engine = SimulationEngine(session, incident.id, incident.seed)
        ctx = ToolContext(session=session, engine=engine, incident=incident, scenario=scenario)

        if name in REMEDIATION_TOOLS:
            result = SandboxExecutor().execute(name, arguments, ctx)
        else:
            parsed = tool.args_model.model_validate(arguments)
            result = tool.run(ctx, parsed)

        session.commit()
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]
    except SandboxViolation as exc:
        session.rollback()
        return [_error(str(exc))]
    except Exception as exc:  # noqa: BLE001 - surface as a tool error, not a transport crash
        session.rollback()
        logger.exception("MCP tool call failed: %s(%s)", name, arguments)
        return [_error(str(exc))]
    finally:
        session.close()


def _error(message: str) -> types.TextContent:
    return types.TextContent(type="text", text=json.dumps({"error": message}))


async def _run() -> None:
    from app.db import init_db

    init_db()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_run())
