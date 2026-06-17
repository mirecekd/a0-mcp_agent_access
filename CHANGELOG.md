# Changelog

All notable changes to this plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2026-06-17

### Fixed

- **Prompt filter never ran.** The original implementation hooked the `@extensible`
  `build_prompt` end point at
  `extensions/python/_functions/extensions/python/system_prompt/_12_mcp_prompt/build_prompt/end/`.
  Agent Zero's extension scanner does not visit that deep `_functions/...` path inside
  plugin directories, so the filter was never loaded for any agent and every profile
  saw every MCP server.
  The filter has been moved to the standard `system_prompt` extension point as
  `_13_filter_mcp_prompt.py`. It runs right after the built-in `_12_mcp_prompt.py`
  (`MCPToolsPrompt`) and rewrites the MCP block already appended to `system_prompt[]`.

- **Server-name mismatch silently dropped all servers.** `MCPConfig` normalizes
  server names (lowercased, non-word characters replaced with underscores), so
  `aws-knowledge` in `settings.json` becomes `aws_knowledge` at runtime, while the
  whitelist in `config.json` keeps the original hyphenated form. The previous
  comparison was a plain `name in allowed`, which never matched and caused profiles
  with explicit AWS whitelists to see no MCP servers at all. The filter now
  normalizes both sides of the comparison the same way Agent Zero does.

- **Plugin config could fail to load for subordinate agents.**
  `helpers/plugins.get_plugin_config()` calls `agent.context.get_data(...)`, which
  can raise when a subordinate's context is not fully initialized. The exception
  was swallowed by `_load_access_map`, leaving `access_map` empty and falling back
  to allow-all. `helpers/access.py` now reads `config.json` directly from the
  plugin directory as a disk fallback when the framework helper fails or returns
  an empty access map.

### Added

- `helpers/__init__.py` and top-level plugin `__init__.py` so the plugin's
  helpers are importable as a regular Python package on every platform, not only
  via PEP 420 namespace packages.

### Removed

- The old non-functional filter at
  `extensions/python/_functions/extensions/python/system_prompt/_12_mcp_prompt/build_prompt/end/_50_filter_mcp_prompt.py`
  and its empty `_functions/` directory tree.

## [1.0.0] - 2026-06-17

### Added

- Initial release.
- Per-profile MCP server whitelist via `config.json` `access_map`.
- Prompt filter extension that hides disallowed MCP servers from each agent's
  system prompt.
- Hard execution gate (`tool_execute_before`) that rejects MCP tool calls whose
  server is not whitelisted for the current profile.
- Wildcard `*` profile entry for the default whitelist.
- WebUI configuration page under Settings → MCP.
