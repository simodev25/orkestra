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
  const [selectedMcp, setSelectedMcp] = useState<CatalogMcpViewModel | null>(null);

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
    <div className="page animate-fade-in">
      {/* Page header */}
      <div className="pagehead">
        <div>
          <h1>MCP Catalog</h1>
          <p>MCP capabilities are sourced from Obot. Orkestra governs visibility, eligibility, and binding.</p>
        </div>
        <div className="pagehead__actions">
          <button
            onClick={handleSyncCatalog}
            disabled={busyKey === "sync"}
            className="btn btn--cyan"
          >
            {busyKey === "sync" ? "Syncing..." : "Sync Catalog"}
          </button>
          <button
            onClick={handleImportCatalog}
            disabled={busyKey === "import"}
            className="btn btn--purple"
          >
            {busyKey === "import" ? "Importing..." : "Import from Obot"}
          </button>
        </div>
      </div>

      {/* Message banner */}
      {message && (
        <div className="glass-panel p-3">
          <p className="text-xs font-mono text-ork-muted">{message}</p>
        </div>
      )}

      {/* Stat cards */}
      <div className="stats">
        <StatCard label="Obot MCPs" value={summary.total} accent="cyan" />
        <StatCard label="Enabled" value={summary.enabled} accent="green" />
        <StatCard label="Restricted" value={summary.restricted} accent="amber" />
        <StatCard label="Critical" value={summary.critical} accent="red" />
        <StatCard label="Approval Required" value={summary.approval} accent="purple" />
        <StatCard label="Hidden from AI Gen" value={summary.aiHidden} />
      </div>

      {/* Filters */}
      <div className="filters" style={{ gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr 1fr" }}>
        <div className="fieldwrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input
            className="field"
            value={filters.search ?? ""}
            onChange={(e) => setFilters((prev) => ({ ...prev, search: e.target.value }))}
            placeholder="Search name / id / purpose"
          />
        </div>
        <select
          className="field"
          value={filters.obot_status}
          onChange={(e) => setFilters((prev) => ({ ...prev, obot_status: e.target.value }))}
        >
          <option value="all">Obot status: all</option>
          <option value="active">active</option>
          <option value="degraded">degraded</option>
          <option value="disabled">disabled</option>
        </select>
        <select
          className="field"
          value={filters.orkestra_status}
          onChange={(e) => setFilters((prev) => ({ ...prev, orkestra_status: e.target.value }))}
        >
          <option value="all">Orkestra status: all</option>
          <option value="enabled">enabled</option>
          <option value="disabled">disabled</option>
          <option value="restricted">restricted</option>
          <option value="hidden">hidden</option>
        </select>
        <select
          className="field"
          value={filters.criticality}
          onChange={(e) => setFilters((prev) => ({ ...prev, criticality: e.target.value }))}
        >
          <option value="all">criticality: all</option>
          <option value="low">low</option>
          <option value="medium">medium</option>
          <option value="high">high</option>
        </select>
        <select
          className="field"
          value={filters.effect_type}
          onChange={(e) => setFilters((prev) => ({ ...prev, effect_type: e.target.value }))}
        >
          <option value="all">effect type: all</option>
          <option value="read">read</option>
          <option value="search">search</option>
          <option value="compute">compute</option>
          <option value="generate">generate</option>
          <option value="validate">validate</option>
          <option value="write">write</option>
          <option value="act">act</option>
        </select>
        <select
          className="field"
          value={filters.approval_required}
          onChange={(e) =>
            setFilters((prev) => ({
              ...prev,
              approval_required: e.target.value as "all" | "true" | "false",
            }))
          }
        >
          <option value="all">approval: all</option>
          <option value="true">required</option>
          <option value="false">not required</option>
        </select>
      </div>

      {/* Split view */}
      <div className="split">
        {/* Table gauche */}
        <div className="tablewrap">
          {loading ? (
            <div style={{ padding: "32px 16px", textAlign: "center" }}>
              <p className="section-title">Loading MCP Catalog...</p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Effect Type</th>
                  <th>Obot State</th>
                  <th>Orkestra State</th>
                  <th>Criticality</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr
                    key={item.obot_server.id}
                    className={selectedMcp?.obot_server.id === item.obot_server.id ? "is-selected" : ""}
                    onClick={() => setSelectedMcp(item)}
                  >
                    <td className="col-name">
                      {item.obot_server.name}
                      <span className="sub">{item.obot_server.id}</span>
                    </td>
                    <td className="col-fam">{item.obot_server.effect_type || "—"}</td>
                    <td><StatusBadge status={item.obot_state} /></td>
                    <td><StatusBadge status={item.orkestra_state} /></td>
                    <td>
                      <span className={`crit crit--${item.obot_server.criticality || "low"}`}>
                        {item.obot_server.criticality || "low"}
                      </span>
                    </td>
                  </tr>
                ))}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: "center", color: "var(--ork-muted-2)", fontFamily: "var(--font-mono)", fontSize: 11.5, padding: "24px 0" }}>
                      No MCPs found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail pane droite */}
        <div className="detail">
          {!selectedMcp ? (
            <div className="detail__empty">
              <span>Select an MCP<br/>to see details</span>
            </div>
          ) : (
            <>
              <div className="detail__head">
                <div className="detail__idrow">
                  <span className="detail__id">{selectedMcp.obot_server.id}</span>
                  <StatusBadge status={selectedMcp.orkestra_state} />
                </div>
                <div className="detail__name">{selectedMcp.obot_server.name}</div>
                {selectedMcp.obot_server.purpose && (
                  <p className="detail__purpose">{selectedMcp.obot_server.purpose}</p>
                )}
                <div className="detail__meta">
                  <span className={`crit crit--${selectedMcp.obot_server.criticality || "low"}`}>
                    {selectedMcp.obot_server.criticality || "low"}
                  </span>
                  {selectedMcp.obot_server.effect_type && (
                    <span className="chip chip--mini">{selectedMcp.obot_server.effect_type}</span>
                  )}
                </div>
              </div>
              <div className="tabpane">
                <div className="kv">
                  <span className="k">MCP ID</span>
                  <span className="v mono">{selectedMcp.obot_server.id}</span>
                  <span className="k">Obot State</span>
                  <span className="v"><StatusBadge status={selectedMcp.obot_state} /></span>
                  <span className="k">Orkestra State</span>
                  <span className="v"><StatusBadge status={selectedMcp.orkestra_state} /></span>
                  <span className="k">Effect Type</span>
                  <span className="v mono">{selectedMcp.obot_server.effect_type || "—"}</span>
                  <span className="k">Criticality</span>
                  <span className="v">
                    <span className={`crit crit--${selectedMcp.obot_server.criticality || "low"}`}>
                      {selectedMcp.obot_server.criticality || "low"}
                    </span>
                  </span>
                  <span className="k">Approval Required</span>
                  <span className="v mono">{selectedMcp.obot_server.approval_required ? "yes" : "no"}</span>
                  <span className="k">Allowed Workflows</span>
                  <span className="v mono">{selectedMcp.orkestra_binding.allowed_workflows.length}</span>
                  <span className="k">Allowed Agent Families</span>
                  <span className="v mono">{selectedMcp.orkestra_binding.allowed_agent_families.length}</span>
                </div>

                {/* Tools preview */}
                {selectedMcp.obot_server.tool_preview && selectedMcp.obot_server.tool_preview.length > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <p className="section-title" style={{ marginBottom: 8 }}>Tools</p>
                    <div className="row flex-wrap">
                      {selectedMcp.obot_server.tool_preview.map((tool) => (
                        <span
                          key={tool.name}
                          title={tool.description ?? tool.name}
                          className="chip chip--mini"
                        >
                          {tool.name}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8 }}>
                  {(() => {
                    const busy =
                      busyKey === `enable:${selectedMcp.obot_server.id}` ||
                      busyKey === `disable:${selectedMcp.obot_server.id}` ||
                      busyKey === `bind:wf:${selectedMcp.obot_server.id}` ||
                      busyKey === `bind:family:${selectedMcp.obot_server.id}`;
                    return (
                      <>
                        <button
                          onClick={() =>
                            selectedMcp.orkestra_binding.enabled_in_orkestra
                              ? handleDisable(selectedMcp.obot_server.id)
                              : handleEnable(selectedMcp.obot_server.id)
                          }
                          disabled={busy}
                          className="btn btn--cyan"
                          style={{ width: "100%", justifyContent: "center" }}
                        >
                          {selectedMcp.orkestra_binding.enabled_in_orkestra ? "Disable in Orkestra" : "Enable in Orkestra"}
                        </button>
                        <button
                          onClick={() => handleBindWorkflow(selectedMcp.obot_server.id)}
                          disabled={busy}
                          className="btn btn--ghost"
                          style={{ width: "100%", justifyContent: "center" }}
                        >
                          Bind to Workflow
                        </button>
                        <button
                          onClick={() => handleBindAgentFamily(selectedMcp.obot_server.id)}
                          disabled={busy}
                          className="btn btn--ghost"
                          style={{ width: "100%", justifyContent: "center" }}
                        >
                          Bind to Agent Family
                        </button>
                      </>
                    );
                  })()}
                  <Link
                    href={`/mcps/${selectedMcp.obot_server.id}`}
                    className="btn btn--ghost"
                    style={{ width: "100%", justifyContent: "center" }}
                  >
                    View Full Details →
                  </Link>
                  {selectedMcp.obot_server.obot_url && (
                    <a
                      href={selectedMcp.obot_server.obot_url}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn--ghost"
                      style={{ width: "100%", justifyContent: "center" }}
                    >
                      View in Obot ↗
                    </a>
                  )}
                  <Link
                    href={`/mcps/${selectedMcp.obot_server.id}/edit`}
                    className="btn btn--ghost"
                    style={{ width: "100%", justifyContent: "center" }}
                  >
                    Edit Orkestra Settings
                  </Link>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
