"""SandboxExecutor: the ONLY code path allowed to mutate simulated infrastructure.

This is a hard allowlist, not a convention. `execute()` refuses anything
outside `ALLOWED_ACTION_TOOLS`, and both allowed tools dispatch exclusively
into `SimulationEngine` methods — never a shell, subprocess, or socket.
"""
from __future__ import annotations

from app.tools.base import ToolContext
from app.tools.registry import get_tool

ALLOWED_ACTION_TOOLS = frozenset({"restart_service", "rollback_deployment"})


class SandboxViolation(RuntimeError):
    pass


class SandboxExecutor:
    def execute(self, tool_name: str, args: dict, ctx: ToolContext) -> dict:
        if tool_name not in ALLOWED_ACTION_TOOLS:
            raise SandboxViolation(
                f"'{tool_name}' is not an allowlisted remediation action. Allowed: {sorted(ALLOWED_ACTION_TOOLS)}"
            )
        tool = get_tool(tool_name)
        parsed_args = tool.args_model.model_validate(args)
        return tool.run(ctx, parsed_args)
