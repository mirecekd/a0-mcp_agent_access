"""Hard gate for MCP tool calls based on the per-agent whitelist.

The system-prompt filter already hides disallowed MCP servers from an agent,
but the MCP handler itself is global, so a model could still *try* to call a
tool it should not have. This extension is the hard barrier: it runs in the
``tool_execute_before`` hook and raises if the agent's profile is not allowed
to use the MCP server that owns the requested tool.

MCP tools are named ``"<server>.<tool>"``. Non-MCP core tools never match and
are always allowed.
"""

from __future__ import annotations

from typing import Any

from helpers.extension import Extension
from helpers.mcp_handler import MCPConfig

from usr.plugins.mcp_agent_access.helpers.access import is_server_allowed, resolve_profile


class McpAccessGate(Extension):
    async def execute(self, tool_name: str = "", tool_args: dict = {}, **kwargs: Any):
        if not self.agent or not tool_name or "." not in tool_name:
            return  # no agent or not an MCP-style tool name

        server_part = tool_name.split(".", 1)[0]

        # Only gate names that are genuinely MCP tools.
        try:
            mcp_config = MCPConfig.get_instance()
            if not mcp_config.has_tool(tool_name):
                return  # not a real MCP tool -> leave to normal dispatch
        except Exception:
            return  # if MCP isn't ready, don't block normal tools

        if is_server_allowed(self.agent, server_part):
            return  # allowed -> proceed

        profile = resolve_profile(self.agent) or "this agent"
        raise PermissionError(
            f"MCP access denied: profile '{profile}' is not allowed to use MCP "
            f"server '{server_part}' (tool '{tool_name}'). This restriction is "
            f"enforced by the mcp_agent_access plugin. Use a different approach "
            f"or ask the user to grant this profile access to '{server_part}'."
        )
