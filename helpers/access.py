"""Access-control logic for the mcp_agent_access plugin.

Resolves which MCP servers a given agent profile is allowed to see in its
system prompt and call at runtime. The mapping is a simple whitelist:

    profile -> [list of allowed MCP server names]

A special ``"*"`` key provides the default whitelist applied to any profile
that has no explicit entry. If neither the profile nor ``"*"`` is configured,
the plugin falls back to *allow-all* so installing it without configuration
never silently hides tools.

The mapping is read from the plugin settings (project/profile/global scope via
``get_plugin_config``) and falls back to ``default_config.yaml``.
"""

from __future__ import annotations

from typing import Any, Iterable

from helpers.print_style import PrintStyle

_CONFIG_KEY = "access_map"
_WILDCARD = "*"


def resolve_profile(agent: Any) -> str:
    """Best-effort extraction of the agent's profile name.

    Tries ``agent.config.profile`` first (the canonical profile id), then a
    few fallbacks, and finally ``"agent0"`` for the top-level agent.
    """
    if agent is None:
        return ""
    # canonical: AgentConfig.profile
    cfg = getattr(agent, "config", None)
    profile = getattr(cfg, "profile", None)
    if isinstance(profile, str) and profile:
        return profile
    # fallbacks
    for attr in ("profile", "agent_name"):
        val = getattr(agent, attr, None)
        if isinstance(val, str) and val:
            return val
    # top-level agent has number 0
    if getattr(agent, "number", None) == 0:
        return "agent0"
    return ""


def _load_access_map(agent: Any) -> dict[str, list[str]]:
    """Load the profile->servers whitelist from plugin config.

    Reads runtime plugin settings first (resolves project/profile scope from
    the agent context), then falls back to the packaged ``default_config.yaml``.
    If get_plugin_config fails (e.g. agent.context not initialized), falls back
    to reading config.json directly from the plugin directory.
    """
    raw: dict[str, Any] | None = None
    try:
        from helpers.plugins import get_plugin_config

        raw = get_plugin_config("mcp_agent_access", agent=agent) or None
    except Exception as exc:  # pragma: no cover - defensive
        PrintStyle.warning(f"[mcp_agent_access] could not read plugin config: {exc}")
        raw = None

    access: Any = None
    if isinstance(raw, dict):
        access = raw.get(_CONFIG_KEY)

    # Disk fallback: read config.json directly from plugin dir when the
    # framework helper failed or returned an empty/missing access_map.
    if not isinstance(access, dict) or not access:
        try:
            import json as _json
            import os as _os

            _here = _os.path.dirname(_os.path.abspath(__file__))
            _plugin_dir = _os.path.dirname(_here)
            _cfg_path = _os.path.join(_plugin_dir, "config.json")
            if _os.path.exists(_cfg_path):
                with open(_cfg_path, "r") as _f:
                    raw = _json.load(_f)
                if isinstance(raw, dict):
                    access = raw.get(_CONFIG_KEY)
        except Exception as exc:  # pragma: no cover - defensive
            PrintStyle.warning(
                f"[mcp_agent_access] disk fallback for config.json failed: {exc}"
            )

    if not isinstance(access, dict):
        return {}

    # normalize: values must be lists of strings
    norm: dict[str, list[str]] = {}
    for profile, servers in access.items():
        if isinstance(servers, str):
            servers = [s.strip() for s in servers.split(",") if s.strip()]
        if isinstance(servers, Iterable):
            norm[str(profile)] = [str(s) for s in servers]
    return norm


def allowed_servers(agent: Any) -> set[str] | None:
    """Return the set of MCP server names allowed for this agent.

    Returns ``None`` to mean "no restriction configured -> allow all".
    """
    access_map = _load_access_map(agent)
    if not access_map:
        return None  # allow-all when unconfigured

    profile = resolve_profile(agent)
    if profile in access_map:
        return set(access_map[profile])
    if _WILDCARD in access_map:
        return set(access_map[_WILDCARD])
    # map exists but neither profile nor wildcard listed -> deny restricted set,
    # but to stay safe we allow-all (explicit deny requires an explicit entry).
    return None


def is_server_allowed(agent: Any, server_name: str) -> bool:
    """True if the given MCP server is visible/callable for this agent."""
    allowed = allowed_servers(agent)
    if allowed is None:
        return True
    return server_name in allowed
