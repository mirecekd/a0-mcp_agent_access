import { createStore } from "/js/AlpineStore.js";
import { fetchApi } from "/js/api.js";

// Store for the MCP Agent Access Control settings UI.
// Edits a profile -> [allowed MCP servers] whitelist held in config.access_map.
// Loads the real configured MCP servers (checkbox per server) and the real
// agent profiles (one row per profile) via the authenticated A0 API.

const model = {
    config: null,
    context: null,
    rows: [],          // [{ profile: string, servers: string[] }]
    knownServers: [],  // names of MCP servers actually configured
    knownProfiles: [], // agent profile keys actually present
    didInit: false,

    async init(config, context) {
        this.config = config;
        this.context = context;
        const map = (config && config.access_map) || {};
        this.rows = Object.keys(map).map((profile) => ({
            profile,
            servers: Array.isArray(map[profile])
                ? [...map[profile]]
                : String(map[profile] || "")
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
        }));
        this.didInit = true;
        await this.loadKnownServers();
        await this.loadKnownProfiles();
    },

    cleanup() {
        this.config = null;
        this.context = null;
        this.rows = [];
        this.knownServers = [];
        this.knownProfiles = [];
        this.didInit = false;
    },

    async loadKnownServers() {
        // authenticated call (adds CSRF + credentials) — plain fetch() gets 403
        try {
            const response = await fetchApi("/mcp_servers_status", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({}),
            });
            const data = await response.json().catch(() => ({}));
            const status = data.status || data.servers || data.mcp_servers || [];
            const names = (Array.isArray(status) ? status : [])
                .map((s) => s.name || s.server || s.id)
                .filter(Boolean);
            this.knownServers = [...new Set(names)];
        } catch (e) {
            this.knownServers = [];
        }
    },

    async loadKnownProfiles() {
        // pull real agent profiles so we can show their proper display names
        // each entry: { key: "aws_architect", label: "AWS Architect" }
        try {
            const response = await fetchApi("/agents", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ action: "list" }),
            });
            const data = await response.json().catch(() => ({}));
            const list = data.ok ? data.data || [] : data.data || data.agents || [];
            this.knownProfiles = (Array.isArray(list) ? list : [])
                .map((p) => ({
                    key: p.key || p.name || p.profile || p.id,
                    label: p.label || p.title || p.name || p.key || "",
                }))
                .filter((p) => p.key);
        } catch (e) {
            this.knownProfiles = [];
        }
    },

    hasKnownServers() {
        return this.knownServers.length > 0;
    },

    hasKnownProfiles() {
        return this.knownProfiles.length > 0;
    },

    // display label for a profile key (falls back to the key itself)
    profileLabel(key) {
        const k = (key || "").trim();
        if (k === "*") return "All other profiles (*)";
        const found = this.knownProfiles.find((p) => p.key === k);
        return found ? found.label : k;
    },

    // Build the full <option> set for a row. Always includes the row's current
    // value as an option, so the <select> can never silently fall back to '*'
    // while knownProfiles is still loading.
    profileOptions(row) {
        const opts = [];
        const seen = new Set();
        const current = (row && row.profile ? String(row.profile) : "").trim();
        for (const p of this.knownProfiles) {
            if (!p || !p.key) continue;
            opts.push({ value: p.key, label: p.label || p.key });
            seen.add(p.key);
        }
        // Ensure the row's current selection has a matching option even when
        // knownProfiles hasn't loaded yet or contains a custom/legacy key.
        if (current && current !== "*" && !seen.has(current)) {
            const label = this.knownProfiles.length === 0
                ? current
                : `${current} (custom)`;
            opts.unshift({ value: current, label });
            seen.add(current);
        }
        // Wildcard option is always last.
        opts.push({ value: "*", label: "All other profiles (*)" });
        return opts;
    },

    // profile keys offered in the picker but not yet used as a row
    availableProfiles() {
        const used = new Set(this.rows.map((r) => (r.profile || "").trim()));
        return this.knownProfiles.filter((p) => !used.has(p.key));
    },

    isChecked(row, serverName) {
        return row.servers.includes(serverName);
    },

    toggleServer(row, serverName) {
        const i = row.servers.indexOf(serverName);
        if (i === -1) row.servers.push(serverName);
        else row.servers.splice(i, 1);
        this.sync();
    },

    // free-text fallback (when MCP server list can't be loaded)
    serversText(row) {
        return row.servers.join(", ");
    },
    setServersText(row, text) {
        row.servers = String(text || "")
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
        this.sync();
    },

    addRow(profile = "") {
        this.rows.push({ profile, servers: [] });
        if (profile) this.sync();
    },

    addAllProfiles() {
        // availableProfiles() returns {key, label} objects — store the key,
        // not the whole object, so the row's <select> can match it.
        for (const p of this.availableProfiles()) {
            this.rows.push({ profile: p.key, servers: [] });
        }
        this.sync();
    },

    addWildcard() {
        if (this.hasWildcard()) return;
        this.rows.push({ profile: "*", servers: [] });
        this.sync();
    },

    hasWildcard() {
        return this.rows.some((r) => (r.profile || "").trim() === "*");
    },

    removeRow(idx) {
        this.rows.splice(idx, 1);
        this.sync();
    },

    sync() {
        if (!this.config) return;
        const map = {};
        for (const row of this.rows) {
            const profile = (row.profile || "").trim();
            if (!profile) continue;
            map[profile] = [...row.servers];
        }
        this.config.access_map = map;
    },
};

export const store = createStore("mcpAgentAccess", model);
