"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { StatCard } from "@/components/ui/stat-card";
import {
  bindToAgentFamily,
  bindToWorkflow,
  disableInOrkestra,
  enableInOrkestra,
  getCatalogStats,
  importFromObot,
  listCatalogItems,
  syncObotCatalog,
} from "@/lib/mcp-catalog/service";
import type { CatalogMcpViewModel, McpCatalogFilters, McpCatalogStats } from "@/lib/mcp-catalog/types";

const DEFAULT_FILTERS: McpCatalogFilters = {
  search: "",
  obot_status: "all",
  orkestra_status: "all",
  criticality: "all",
  effect_type: "all",
  approval_required: "all",
  allowed_workflow: "",
  allowed_agent_family: "",
  hidden_from_ai_generator: "all",
};


export default function McpCatalogPage() {
  const [items, setItems] = useState<CatalogMcpViewModel[]>([]);
  const [stats, setStats] = useState<McpCatalogStats | null>(null);
  const [filters, setFilters] = useState<McpCatalogFilters>(DEFAULT_FILTERS);
  const [loading, setLoading] = useState(true);
  const [refreshToken, setRefreshToken] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([listCatalogItems(filters), getCatalogStats()])
      .then(([catalog, catalogStats]) => {
        if (cancelled) return;
        setItems(catalog);
        setStats(catalogStats);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        const errorMessage = error instanceof Error ? error.message : "Failed to load MCP Catalog";
        setMessage(errorMessage);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [filters, refreshToken]);

  function refreshCatalog() {
    setRefreshToken((value) => value + 1);
  }

  async function runGlobalAction(actionKey: string, action: () => Promise<void>) {
    setBusyKey(actionKey);
    setMessage(null);
    try {
      await action();
      refreshCatalog();
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleSyncCatalog() {
    await runGlobalAction("sync", async () => {
      const result = await syncObotCatalog();
      setMessage(
        `Sync complete: ${result.total_obot_servers} Obot MCP(s), ${result.existing_bindings_updated} binding(s) updated.`,
      );
    });
  }

  async function handleImportCatalog() {
    await runGlobalAction("import", async () => {
      const result = await importFromObot();
      setMessage(
        `Import complete: ${result.imported_count} imported, ${result.updated_count} updated.`,
      );
    });
  }

  async function handleEnable(obotServerId: string) {
    await runGlobalAction(`enable:${obotServerId}`, async () => {
      await enableInOrkestra(obotServerId);
      setMessage(`Enabled ${obotServerId} in Orkestra.`);
    });
  }

  async function handleDisable(obotServerId: string) {
    await runGlobalAction(`disable:${obotServerId}`, async () => {
      await disableInOrkestra(obotServerId);
      setMessage(`Disabled ${obotServerId} in Orkestra.`);
    });
  }

  async function handleBindWorkflow(obotServerId: string) {
    const workflowId = window.prompt("Workflow ID to bind:");
    if (!workflowId) return;
    await runGlobalAction(`bind:wf:${obotServerId}`, async () => {
      await bindToWorkflow(obotServerId, workflowId.trim());
      setMessage(`Bound ${obotServerId} to workflow ${workflowId.trim()}.`);
    });
  }

  async function handleBindAgentFamily(obotServerId: string) {
    const agentFamily = window.prompt("Agent family to bind:");
    if (!agentFamily) return;
    await runGlobalAction(`bind:family:${obotServerId}`, async () => {
      await bindToAgentFamily(obotServerId, agentFamily.trim());
      setMessage(`Bound ${obotServerId} to agent family ${agentFamily.trim()}.`);
    });
  }

  const summary = useMemo(
    () => ({
      total: stats?.obot_total ?? 0,
      enabled: stats?.orkestra_enabled ?? 0,
      restricted: stats?.orkestra_restricted ?? 0,
      critical: stats?.critical ?? 0,
      approval: stats?.approval_required ?? 0,
      aiHidden: stats?.hidden_from_ai_generator ?? 0,
    }),
    [stats],
  );

  return (
    <div className="p-6 max-w-[1500px] mx-auto space-y-5 animate-fade-in">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ork-text tracking-wide">MCP Catalog</h1>
          <p className="text-xs text-ork-dim font-mono mt-1">
            MCP capabilities are sourced from Obot. Orkestra governs visibility, eligibility, and binding.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={handleSyncCatalog}
            disabled={busyKey === "sync"}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/40 text-ork-cyan bg-ork-cyan/10 disabled:opacity-50"
          >
            {busyKey === "sync" ? "Syncing..." : "Sync Catalog"}
          </button>
          <button
            onClick={handleImportCatalog}
            disabled={busyKey === "import"}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-purple/40 text-ork-purple bg-ork-purple/10 disabled:opacity-50"
          >
            {busyKey === "import" ? "Importing..." : "Import from Obot"}
          </button>
        </div>
      </div>

      {message && (
        <div className="glass-panel p-3">
          <p className="text-xs font-mono text-ork-muted">{message}</p>
        </div>
      )}

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        <StatCard label="Obot MCPs" value={summary.total} accent="cyan" />
        <StatCard label="Enabled in Orkestra" value={summary.enabled} accent="green" />
        <StatCard label="Restricted" value={summary.restricted} accent="amber" />
        <StatCard label="Critical" value={summary.critical} accent="red" />
        <StatCard label="Approval Required" value={summary.approval} accent="purple" />
        <StatCard label="Hidden from AI Gen" value={summary.aiHidden} />
      </div>

      <div className="glass-panel p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <input
            value={filters.search ?? ""}
            onChange={(e) => setFilters((prev) => ({ ...prev, search: e.target.value }))}
            placeholder="Search name / id / purpose"
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          />
          <select
            value={filters.obot_status}
            onChange={(e) => setFilters((prev) => ({ ...prev, obot_status: e.target.value }))}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          >
            <option value="all">Obot status: all</option>
            <option value="active">Obot status: active</option>
            <option value="degraded">Obot status: degraded</option>
            <option value="disabled">Obot status: disabled</option>
          </select>
          <select
            value={filters.orkestra_status}
            onChange={(e) => setFilters((prev) => ({ ...prev, orkestra_status: e.target.value }))}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          >
            <option value="all">Orkestra status: all</option>
            <option value="enabled">enabled</option>
            <option value="disabled">disabled</option>
            <option value="restricted">restricted</option>
            <option value="hidden">hidden</option>
          </select>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <select
            value={filters.criticality}
            onChange={(e) => setFilters((prev) => ({ ...prev, criticality: e.target.value }))}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          >
            <option value="all">Criticality: all</option>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
          <select
            value={filters.effect_type}
            onChange={(e) => setFilters((prev) => ({ ...prev, effect_type: e.target.value }))}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          >
            <option value="all">Effect type: all</option>
            <option value="read">read</option>
            <option value="search">search</option>
            <option value="compute">compute</option>
            <option value="generate">generate</option>
            <option value="validate">validate</option>
            <option value="write">write</option>
            <option value="act">act</option>
          </select>
          <select
            value={filters.approval_required}
            onChange={(e) =>
              setFilters((prev) => ({
                ...prev,
                approval_required: e.target.value as "all" | "true" | "false",
              }))
            }
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          >
            <option value="all">Approval required: all</option>
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
          <select
            value={filters.hidden_from_ai_generator}
            onChange={(e) =>
              setFilters((prev) => ({
                ...prev,
                hidden_from_ai_generator: e.target.value as "all" | "true" | "false",
              }))
            }
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          >
            <option value="all">Hidden from AI generator: all</option>
            <option value="true">true</option>
            <option value="false">false</option>
          </select>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <input
            value={filters.allowed_workflow ?? ""}
            onChange={(e) => setFilters((prev) => ({ ...prev, allowed_workflow: e.target.value }))}
            placeholder="Filter by allowed workflow"
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          />
          <input
            value={filters.allowed_agent_family ?? ""}
            onChange={(e) => setFilters((prev) => ({ ...prev, allowed_agent_family: e.target.value }))}
            placeholder="Filter by allowed agent family"
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          />
        </div>
      </div>

      {loading ? (
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">Loading MCP Catalog...</div>
      ) : (
        <div className="glass-panel overflow-x-auto">
          <table className="w-full min-w-[1400px] text-xs">
            <thead className="bg-ork-surface border-b border-ork-border">
              <tr className="text-left font-mono uppercase tracking-wider text-ork-dim">
                <th className="p-3">Name</th>
                <th className="p-3">MCP ID / Obot Server ID</th>
                <th className="p-3">Purpose</th>
                <th className="p-3">Tools</th>
                <th className="p-3">Effect type</th>
                <th className="p-3">Obot state</th>
                <th className="p-3">Orkestra state</th>
                <th className="p-3">Criticality</th>
                <th className="p-3">Approval required</th>
                <th className="p-3">Allowed workflows</th>
                <th className="p-3">Allowed agent families</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => {
                const busy =
                  busyKey === `enable:${item.obot_server.id}` ||
                  busyKey === `disable:${item.obot_server.id}` ||
                  busyKey === `bind:wf:${item.obot_server.id}` ||
                  busyKey === `bind:family:${item.obot_server.id}`;
                return (
                  <tr key={item.obot_server.id} className="border-b border-ork-border/50 align-top">
                    <td className="p-3 font-medium text-ork-text">{item.obot_server.name}</td>
                    <td className="p-3 font-mono text-ork-cyan">{item.obot_server.id}</td>
                    <td className="p-3 text-ork-muted max-w-[280px]">{item.obot_server.purpose}</td>
                    <td className="p-3">
                      {(item.obot_server.tool_preview ?? []).length === 0 ? (
                        <span className="text-ork-dim font-mono text-[10px]">—</span>
                      ) : (
                        <div className="flex flex-wrap gap-1">
                          {item.obot_server.tool_preview.map((tool) => (
                            <span
                              key={tool.name}
                              title={tool.description ?? tool.name}
                              className="text-[10px] font-mono text-ork-cyan bg-ork-cyan/10 border border-ork-cyan/20 px-1.5 py-0.5 rounded cursor-default"
                            >
                              {tool.name}
                            </span>
                          ))}
                        </div>
                      )}
                    </td>
                    <td className="p-3 font-mono">{item.obot_server.effect_type}</td>
                    <td className="p-3">
                      <div className="flex items-center gap-1 flex-wrap">
                        <StatusBadge status={item.obot_state} />
                        {item.obot_server.health_status && <StatusBadge status={item.obot_server.health_status} />}
                      </div>
                    </td>
                    <td className="p-3">
                      <StatusBadge status={item.orkestra_state} />
                    </td>
                    <td className="p-3 font-mono">{item.obot_server.criticality}</td>
                    <td className="p-3 font-mono">{item.obot_server.approval_required ? "yes" : "no"}</td>
                    <td className="p-3 font-mono">{item.orkestra_binding.allowed_workflows.length}</td>
                    <td className="p-3 font-mono">{item.orkestra_binding.allowed_agent_families.length}</td>
                    <td className="p-3">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Link
                          href={`/mcps/${item.obot_server.id}`}
                          className="px-2 py-1 border border-ork-border rounded text-[10px] font-mono uppercase tracking-wider text-ork-muted hover:text-ork-text"
                        >
                          View details
                        </Link>
                        <a
                          href={item.obot_server.obot_url ?? "#"}
                          target="_blank"
                          rel="noreferrer"
                          className={`px-2 py-1 border rounded text-[10px] font-mono uppercase tracking-wider ${
                            item.obot_server.obot_url
                              ? "border-ork-purple/30 text-ork-purple"
                              : "border-ork-border text-ork-dim pointer-events-none"
                          }`}
                        >
                          View in Obot
                        </a>
                        <button
                          onClick={() =>
                            item.orkestra_binding.enabled_in_orkestra
                              ? handleDisable(item.obot_server.id)
                              : handleEnable(item.obot_server.id)
                          }
                          disabled={busy}
                          className="px-2 py-1 border border-ork-cyan/30 rounded text-[10px] font-mono uppercase tracking-wider text-ork-cyan disabled:opacity-50"
                        >
                          {item.orkestra_binding.enabled_in_orkestra ? "Disable in Orkestra" : "Enable in Orkestra"}
                        </button>
                        <button
                          onClick={() => handleBindWorkflow(item.obot_server.id)}
                          disabled={busy}
                          className="px-2 py-1 border border-ork-amber/30 rounded text-[10px] font-mono uppercase tracking-wider text-ork-amber disabled:opacity-50"
                        >
                          Bind to workflow
                        </button>
                        <button
                          onClick={() => handleBindAgentFamily(item.obot_server.id)}
                          disabled={busy}
                          className="px-2 py-1 border border-ork-green/30 rounded text-[10px] font-mono uppercase tracking-wider text-ork-green disabled:opacity-50"
                        >
                          Bind to agent family
                        </button>
                        <Link
                          href={`/mcps/${item.obot_server.id}/edit`}
                          className="px-2 py-1 border border-ork-border rounded text-[10px] font-mono uppercase tracking-wider text-ork-muted hover:text-ork-text"
                        >
                          Edit Orkestra settings
                        </Link>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
