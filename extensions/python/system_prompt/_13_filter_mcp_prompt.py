"""Filter the MCP tools system-prompt block per agent profile.

Runs after MCPToolsPrompt (_12_mcp_prompt.py) at the standard ``system_prompt``
extension point. MCPToolsPrompt appends the full MCP tools block (every server)
to ``system_prompt[]``. This extension finds that block in the list and rewrites
it so the current agent only sees the MCP servers its profile is allowed to use,
based on the plugin whitelist.

If the plugin has no whitelist configured, or the profile/wildcard imposes no
restriction, the original block is left untouched (allow-all).

Note: this lives at the standard ``system_prompt`` extension point because A0
does not scan deep ``_functions/.../build_prompt/end/`` paths inside plugins.
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
    async def execute(self, system_prompt: list[str] = [], loop_data=None, **kwargs: Any):
        if not self.agent or not isinstance(system_prompt, list) or not system_prompt:
            return

        allowed = allowed_servers(self.agent)
        if allowed is None:
            return  # no restriction configured -> leave as-is

        # Find the MCP block (last entry that starts with our prefix)
        idx = -1
        for i in range(len(system_prompt) - 1, -1, -1):
            entry = system_prompt[i]
            if isinstance(entry, str) and entry.startswith(_PREFIX):
                idx = i
                break
        if idx < 0:
            return  # no MCP block to filter

        try:
            mcp_config = MCPConfig.get_instance()
            existing = [s.name for s in mcp_config.servers]
            # MCPConfig normalizes names: lowercased, non-word chars -> underscore.
            # Allowed map (config.json) typically uses the original form (e.g.
            # "aws-knowledge"), so normalize allowed names the same way before
            # comparison or no server will match.
            import re as _re

            def _norm(_n: str) -> str:
                return _re.sub(r"[^\w]", "_", str(_n).strip().lower(), flags=_re.UNICODE)

            allowed_norm = {_norm(a) for a in allowed}
            keep = [name for name in existing if name in allowed_norm or _norm(name) in allowed_norm]

            if not keep:
                # remove the block entirely - this agent has no allowed servers
                system_prompt.pop(idx)
                return

            blocks: list[str] = []
            for name in keep:
                block = mcp_config.get_tools_prompt(server_name=name)
                if block.startswith(_PREFIX):
                    block = block[len(_PREFIX):]
                block = block.strip("\n")
                if block:
                    blocks.append(block)

            if blocks:
                system_prompt[idx] = _PREFIX + "\n\n".join(blocks) + "\n"
            else:
                system_prompt.pop(idx)
        except Exception as exc:  # pragma: no cover - defensive
            PrintStyle.warning(
                f"[mcp_agent_access] prompt filter failed, leaving MCP prompt unchanged: {exc}"
            )
