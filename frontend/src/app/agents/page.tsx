"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import { StatCard } from "@/components/ui/stat-card";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";
import { GenerateAgentModal } from "@/components/agents/generate-agent-modal";
import {
  deleteAgent,
  getAgentHistory,
  getAgentRegistryStats,
  listAgents,
  listMcpCatalogForAgentDesign,
  restoreAgent,
} from "@/lib/agent-registry/service";
import type {
  AgentDefinition,
  AgentRegistryFilters,
  AgentRegistryStats,
  McpCatalogSummary,
} from "@/lib/agent-registry/types";
import { listFamilies } from "@/lib/families/service";
import type { FamilyDefinition } from "@/lib/families/types";
import { importAllDefinitions } from "@/lib/definitions/service";
import type { ImportAllResult } from "@/lib/definitions/service";

const DEFAULT_STATS: AgentRegistryStats = {
  total_agents: 0,
  active_agents: 0,
  tested_agents: 0,
  deprecated_agents: 0,
  current_workflow_agents: 0,
};

export default function AgentRegistryPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm font-mono text-ork-cyan">Loading Agent Registry...</div>}>
      <AgentRegistryPageContent />
    </Suspense>
  );
}

function AgentRegistryPageContent() {
  const searchParams = useSearchParams();
  const workflowId = searchParams.get("workflow") || "";

  const [filters, setFilters] = useState<AgentRegistryFilters>({
    q: "",
    family: "all",
    status: "all",
    criticality: "all",
    cost_profile: "all",
    mcp_id: "",
    workflow_id: workflowId || undefined,
    used_in_workflow_only: false,
  });
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [stats, setStats] = useState<AgentRegistryStats>(DEFAULT_STATS);
  const [catalogMcps, setCatalogMcps] = useState<McpCatalogSummary[]>([]);
  const [families, setFamilies] = useState<FamilyDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [aiModalOpen, setAiModalOpen] = useState(false);
  const [deletingAgentId, setDeletingAgentId] = useState<string | null>(null);
  const [agentPendingDelete, setAgentPendingDelete] = useState<AgentDefinition | null>(null);
  const [historyAgent, setHistoryAgent] = useState<AgentDefinition | null>(null);
  const [agentHistory, setAgentHistory] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<AgentDefinition | null>(null);
  const [activeTab, setActiveTab] = useState<"details" | "skills">("details");
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<string | null>(null);

  useEffect(() => {
    setActiveTab("details");
  }, [selectedAgent?.id]);

  async function loadAll(nextFilters: AgentRegistryFilters) {
    setLoading(true);
    setError(null);
    try {
      const [nextAgents, nextStats, nextMcps, nextFamilies] = await Promise.all([
        listAgents(nextFilters),
        getAgentRegistryStats(nextFilters.workflow_id),
        listMcpCatalogForAgentDesign(),
        listFamilies(),
      ]);
      setAgents(nextAgents);
      setStats(nextStats);
      setCatalogMcps(nextMcps);
      setFamilies(nextFamilies);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load Agent Registry");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const merged = { ...filters, workflow_id: workflowId || undefined };
    setFilters(merged);
    void loadAll(merged);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workflowId]);

  async function applyFilters() {
    await loadAll(filters);
  }

  async function handleImportAll() {
    setImporting(true);
    setImportResult(null);
    try {
      const result = await importAllDefinitions();
      const errCount = result.errors.length;
      setImportResult(
        `✅ ${result.created} created, ${result.updated} updated, ${result.skipped} skipped` +
        (errCount ? ` — ⚠ ${errCount} error(s)` : "")
      );
      await loadAll(filters);
    } catch (err: unknown) {
      setImportResult(`❌ ${err instanceof Error ? err.message : "Import failed"}`);
    } finally {
      setImporting(false);
    }
  }

  function updateFilter<K extends keyof AgentRegistryFilters>(key: K, value: AgentRegistryFilters[K]) {
    setFilters((prev) => ({ ...prev, [key]: value }));
  }

  async function openAgentHistory(agent: AgentDefinition) {
    setHistoryAgent(agent);
    setHistoryLoading(true);
    try {
      const history = await getAgentHistory(agent.id);
      setAgentHistory(history);
    } catch {
      setAgentHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function confirmDeleteAgent() {
    if (!agentPendingDelete) return;
    setDeletingAgentId(agentPendingDelete.id);
    setError(null);
    try {
      await deleteAgent(agentPendingDelete.id);
      setAgentPendingDelete(null);
      await loadAll(filters);
    } catch (err: unknown) {
      setAgentPendingDelete(null);
      setError(err instanceof Error ? err.message : "Failed to delete agent");
    } finally {
      setDeletingAgentId(null);
    }
  }

  return (
    <div className="page animate-fade-in">
      {/* Page header */}
      <div className="pagehead">
        <div>
          <h1>Agent Registry</h1>
          <p>Governed registry of specialized agents with mission, MCP permissions, contracts, lifecycle, and reliability metadata.</p>
        </div>
        <div className="pagehead__actions">
          <Link href="/agents/new" className="btn btn--cyan">+ Add Agent</Link>
          <button
            onClick={() => void handleImportAll()}
            disabled={importing}
            className="btn btn--amber"
          >
            {importing ? "Importing…" : "⬆ Import All"}
          </button>
          <button onClick={() => setAiModalOpen(true)} className="btn btn--purple">✦ Generate</button>
        </div>
      </div>

      {importResult && (
        <div style={{
          padding: "8px 12px",
          background: "var(--ork-surface)",
          border: "1px solid var(--ork-border)",
          borderRadius: 6,
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          color: "var(--ork-text)",
          marginBottom: 4,
        }}>
          {importResult}
        </div>
      )}

      {/* Stat cards */}
      <div className="stats">
        <StatCard label="Active"      value={stats.active_agents}     accent="green"  />
        <StatCard label="Tested"      value={stats.tested_agents}     accent="cyan"   />
        <StatCard label="Deprecated"  value={stats.deprecated_agents} accent="amber"  />
        <StatCard label="In Workflow" value={stats.current_workflow_agents} accent="purple" />
      </div>

      {/* Filters */}
      <div className="filters" style={{ gridTemplateColumns: "2fr 1fr 1fr 1fr auto" }}>
        <div className="fieldwrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
          <input
            className="field"
            value={filters.q ?? ""}
            onChange={(e) => updateFilter("q", e.target.value)}
            placeholder="Search name, id, purpose, skill"
          />
        </div>
        <select className="field" value={filters.family ?? "all"} onChange={(e) => updateFilter("family", e.target.value)}>
          <option value="all">family: all</option>
          {families.map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
        </select>
        <select className="field" value={filters.status ?? "all"} onChange={(e) => updateFilter("status", e.target.value)}>
          <option value="all">status: all</option>
          {["draft","designed","tested","registered","active","deprecated","disabled","archived"].map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select className="field" value={filters.criticality ?? "all"} onChange={(e) => updateFilter("criticality", e.target.value)}>
          <option value="all">criticality: all</option>
          {["low","medium","high","critical"].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <button className="btn btn--cyan" onClick={applyFilters}>Apply</button>
      </div>

      {/* Split view */}
      <div className="split">
        {/* Table */}
        <div className="tablewrap">
          {loading ? (
            <div style={{ padding: "32px 16px", textAlign: "center" }}>
              <p className="section-title">Loading agents...</p>
            </div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Family</th>
                  <th>Status</th>
                  <th>Criticality</th>
                  <th>Version</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {agents.map((agent) => (
                  <tr
                    key={agent.id}
                    className={selectedAgent?.id === agent.id ? "is-selected" : ""}
                    onClick={() => setSelectedAgent(agent)}
                  >
                    <td className="col-name">
                      {agent.name}
                      <span className="sub">{agent.id}</span>
                    </td>
                    <td className="col-fam">{agent.family?.label || agent.family_id}</td>
                    <td><StatusBadge status={agent.status} /></td>
                    <td>
                      <span className={`crit crit--${agent.criticality || "low"}`}>
                        {agent.criticality || "low"}
                      </span>
                    </td>
                    <td className="col-fam">{agent.version}</td>
                    <td>
                      <div className="row" onClick={(e) => e.stopPropagation()}>
                        <Link href={`/agents/${agent.id}`} className="btn btn--ghost" style={{ height: 22, fontSize: 11, padding: "0 7px" }}>view</Link>
                        <button
                          onClick={() => setAgentPendingDelete(agent)}
                          className="btn btn--ghost"
                          style={{ height: 22, fontSize: 11, padding: "0 7px", color: "var(--ork-red)" }}
                        >del</button>
                      </div>
                    </td>
                  </tr>
                ))}
                {agents.length === 0 && (
                  <tr><td colSpan={6} style={{ textAlign: "center", color: "var(--ork-muted-2)", fontFamily: "var(--font-mono)", fontSize: 11.5, padding: "24px 0" }}>No agents found</td></tr>
                )}
              </tbody>
            </table>
          )}
        </div>

        {/* Detail pane */}
        <div className="detail">
          {!selectedAgent ? (
            <div className="detail__empty">
              <span>Select an agent<br/>to see details</span>
            </div>
          ) : (
            <>
              <div className="detail__head">
                <div className="detail__idrow">
                  <span className="detail__id">{selectedAgent.id}</span>
                  <StatusBadge status={selectedAgent.status} />
                </div>
                <div className="detail__name">{selectedAgent.name}</div>
                {selectedAgent.purpose && (
                  <p className="detail__purpose">{selectedAgent.purpose}</p>
                )}
                <div className="detail__meta">
                  <span className={`crit crit--${selectedAgent.criticality || "low"}`}>{selectedAgent.criticality || "low"}</span>
                  <span className="chip chip--mini">{selectedAgent.family?.label || selectedAgent.family_id}</span>
                  {selectedAgent.version && <span className="chip chip--mini">v{selectedAgent.version}</span>}
                </div>
              </div>
              <div className="tabs">
                <button
                  className={`tabs__btn${activeTab === "details" ? " tabs__btn--active" : ""}`}
                  onClick={() => setActiveTab("details")}
                >Details</button>
                <button
                  className={`tabs__btn${activeTab === "skills" ? " tabs__btn--active" : ""}`}
                  onClick={() => setActiveTab("skills")}
                >Skills</button>
              </div>
              <div className="tabpane">
                {activeTab === "details" && (
                  <>
                    <div className="kv">
                      <span className="k">Agent ID</span><span className="v mono">{selectedAgent.id}</span>
                      <span className="k">Family</span><span className="v">{selectedAgent.family?.label || selectedAgent.family_id}</span>
                      <span className="k">Status</span><span className="v"><StatusBadge status={selectedAgent.status} /></span>
                      <span className="k">Version</span><span className="v mono">{selectedAgent.version || "—"}</span>
                      <span className="k">Criticality</span><span className="v"><span className={`crit crit--${selectedAgent.criticality || "low"}`}>{selectedAgent.criticality || "low"}</span></span>
                      <span className="k">Cost Profile</span><span className="v mono">{selectedAgent.cost_profile || "—"}</span>
                      {selectedAgent.llm_model && <><span className="k">LLM Model</span><span className="v mono">{selectedAgent.llm_model}</span></>}
                    </div>
                    {selectedAgent.skill_ids && selectedAgent.skill_ids.length > 0 && (
                      <div style={{ marginTop: 16 }}>
                        <p className="section-title" style={{ marginBottom: 8 }}>Skills</p>
                        <div className="row flex-wrap">
                          {selectedAgent.skill_ids.map((s: string) => (
                            <span key={s} className="chip chip--mini">{s}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    <div style={{ marginTop: 16 }}>
                      <Link href={`/agents/${selectedAgent.id}`} className="btn btn--cyan" style={{ width: "100%", justifyContent: "center" }}>
                        View Full Details →
                      </Link>
                    </div>
                  </>
                )}
                {activeTab === "skills" && (
                  <div>
                    {selectedAgent.skill_ids && selectedAgent.skill_ids.length > 0 ? (
                      <>
                        <p className="section-title" style={{ marginBottom: 8 }}>Skills</p>
                        <div className="row flex-wrap">
                          {selectedAgent.skill_ids.map((s: string) => (
                            <span key={s} className="chip chip--mini">{s}</span>
                          ))}
                        </div>
                      </>
                    ) : (
                      <p className="dim" style={{ fontFamily: "var(--font-mono)", fontSize: 11.5 }}>No skills defined</p>
                    )}
                    <div style={{ marginTop: 16 }}>
                      <Link href={`/agents/${selectedAgent.id}`} className="btn btn--cyan" style={{ width: "100%", justifyContent: "center" }}>
                        View Full Details →
                      </Link>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {/* Modals (logique inchangée) */}
      <GenerateAgentModal
        open={aiModalOpen}
        onClose={() => setAiModalOpen(false)}
        onSaved={() => {
          void loadAll(filters);
        }}
      />

      <ConfirmDangerDialog
        open={Boolean(agentPendingDelete)}
        title="Delete Agent"
        description="This removes the agent definition from Orkestra Registry. This action cannot be undone."
        targetLabel={
          agentPendingDelete ? `${agentPendingDelete.name} (${agentPendingDelete.id})` : undefined
        }
        confirmLabel="Delete Agent"
        loading={Boolean(agentPendingDelete && deletingAgentId === agentPendingDelete.id)}
        onCancel={() => {
          if (deletingAgentId) return;
          setAgentPendingDelete(null);
        }}
        onConfirm={() => void confirmDeleteAgent()}
      />

      {historyAgent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="glass-panel w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-mono font-semibold text-ork-text">
                Version History — {historyAgent.name}
              </h2>
              <button
                onClick={() => setHistoryAgent(null)}
                className="text-xs font-mono text-ork-dim hover:text-ork-text"
              >
                Close
              </button>
            </div>
            {historyLoading ? (
              <p className="text-xs font-mono text-ork-cyan">Loading history...</p>
            ) : agentHistory.length === 0 ? (
              <p className="text-xs font-mono text-ork-dim">No history yet. History is recorded on each update.</p>
            ) : (
              <table className="w-full text-xs font-mono">
                <thead className="border-b border-ork-border/60 text-ork-dim">
                  <tr>
                    <th className="p-2 text-left">version</th>
                    <th className="p-2 text-left">name</th>
                    <th className="p-2 text-left">family</th>
                    <th className="p-2 text-left">status</th>
                    <th className="p-2 text-left">replaced_at</th>
                    <th className="p-2 text-left">action</th>
                  </tr>
                </thead>
                <tbody>
                  {agentHistory.map((h) => (
                    <tr key={h.id} className="border-b border-ork-border/30">
                      <td className="p-2 text-ork-cyan">{h.version}</td>
                      <td className="p-2 text-ork-text">{h.name}</td>
                      <td className="p-2 text-ork-muted">{h.family_id}</td>
                      <td className="p-2 text-ork-muted">{h.status}</td>
                      <td className="p-2 text-ork-dim">{new Date(h.replaced_at).toLocaleString()}</td>
                      <td className="p-2">
                        <button
                          onClick={async () => {
                            await restoreAgent(historyAgent.id, h.id);
                            setHistoryAgent(null);
                            void loadAll(filters);
                          }}
                          className="text-ork-cyan hover:underline text-[10px]"
                        >
                          Restore
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
