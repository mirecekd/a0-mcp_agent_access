"""Filter the MCP tools system-prompt block per agent profile.

Hooks the ``end`` of the ``@extensible`` ``build_prompt`` function in
``extensions/python/system_prompt/_12_mcp_prompt.py``. That core function
returns the full MCP tools prompt (every server). Here we rewrite the result
so the current agent only sees the MCP servers its profile is allowed to use,
based on the plugin whitelist.

If the plugin has no whitelist configured, or the profile/wildcard imposes no
restriction, the original result is left untouched (allow-all).
"""

from __future__ import annotations

from typing import Any

from helpers.extension import Extension
from helpers.mcp_handler import MCPConfig
from helpers.print_style import PrintStyle

from usr.plugins.mcp_agent_access.helpers.access import allowed_servers

# Must match the prefix produced by MCPConfig.get_tools_prompt()
_PREFIX = '## "Remote (MCP Server) Agent Tools" available:\n\n'


class FilterMcpPrompt(Extension):
    async def execute(self, **kwargs: Any):
        data = kwargs.get("data") or {}
        # positional args of build_prompt(agent): args[0] is the agent
        args = data.get("args") or []
        agent = args[0] if args else self.agent
        if agent is None:
            return

        # current full MCP prompt produced by the core function
        current = data.get("result")
        if not isinstance(current, str) or not current.strip():
            return  # nothing to filter

        allowed = allowed_servers(agent)
        if allowed is None:
            return  # no restriction configured -> leave as-is

        try:
            mcp_config = MCPConfig.get_instance()
            existing = [s.name for s in mcp_config.servers]
            keep = [name for name in existing if name in allowed]

            if not keep:
                data["result"] = ""  # this agent sees no MCP servers
                return

            blocks: list[str] = []
            for name in keep:
                block = mcp_config.get_tools_prompt(server_name=name)
                if block.startswith(_PREFIX):
                    block = block[len(_PREFIX):]
                block = block.strip("\n")
                if block:
                    blocks.append(block)

            data["result"] = _PREFIX + "\n\n".join(blocks) + "\n" if blocks else ""
        except Exception as exc:  # pragma: no cover - defensive, never break prompt
            PrintStyle.warning(
                f"[mcp_agent_access] prompt filter failed, leaving MCP prompt unchanged: {exc}"
            )
            return
