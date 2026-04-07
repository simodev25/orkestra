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
    <div className="p-6 max-w-[1500px] mx-auto space-y-5 animate-fade-in">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ork-text tracking-wide">Agent Registry</h1>
          <p className="text-xs text-ork-dim font-mono mt-1">
            Governed registry of specialized agents with mission, MCP permissions, contracts, lifecycle, and
            reliability metadata.
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href="/agents/new"
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10"
          >
            Add Agent
          </Link>
          <button
            onClick={() => setAiModalOpen(true)}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-purple/30 text-ork-purple bg-ork-purple/10"
          >
            Generate Agent with AI
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard label="Agents actifs" value={stats.active_agents} accent="green" />
        <StatCard label="Agents testés" value={stats.tested_agents} accent="cyan" />
        <StatCard label="Agents dépréciés" value={stats.deprecated_agents} accent="amber" />
        <StatCard
          label={workflowId ? `Agents workflow ${workflowId}` : "Agents workflow courant"}
          value={workflowId ? stats.current_workflow_agents : 0}
          accent="purple"
        />
      </div>

      <div className="glass-panel p-4 space-y-3">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
          <input
            value={filters.q ?? ""}
            onChange={(e) => updateFilter("q", e.target.value)}
            placeholder="Search name, id, purpose, skill"
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          />
          <select
            value={filters.family ?? "all"}
            onChange={(e) => updateFilter("family", e.target.value)}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          >
            <option value="all">family: all</option>
            {families.map((f) => (
              <option key={f.id} value={f.id}>
                {f.label} ({f.id})
              </option>
            ))}
          </select>
          <select
            value={filters.status ?? "all"}
            onChange={(e) => updateFilter("status", e.target.value)}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          >
            <option value="all">status: all</option>
            <option value="draft">draft</option>
            <option value="designed">designed</option>
            <option value="tested">tested</option>
            <option value="registered">registered</option>
            <option value="active">active</option>
            <option value="deprecated">deprecated</option>
            <option value="disabled">disabled</option>
            <option value="archived">archived</option>
          </select>
          <select
            value={filters.criticality ?? "all"}
            onChange={(e) => updateFilter("criticality", e.target.value)}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          >
            <option value="all">criticality: all</option>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
            <option value="critical">critical</option>
          </select>
          <select
            value={filters.cost_profile ?? "all"}
            onChange={(e) => updateFilter("cost_profile", e.target.value)}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          >
            <option value="all">cost_profile: all</option>
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
            <option value="variable">variable</option>
          </select>
          <select
            value={filters.mcp_id ?? ""}
            onChange={(e) => updateFilter("mcp_id", e.target.value)}
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          >
            <option value="">MCP autorisé: all</option>
            {catalogMcps.map((mcp) => (
              <option key={mcp.id} value={mcp.id}>
                {mcp.name} ({mcp.id})
              </option>
            ))}
          </select>
          <input
            value={filters.workflow_id ?? ""}
            onChange={(e) => updateFilter("workflow_id", e.target.value || undefined)}
            placeholder="workflow id"
            className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          />
          <label className="flex items-center gap-2 px-3 py-2 border border-ork-border rounded text-xs font-mono">
            <input
              type="checkbox"
              checked={Boolean(filters.used_in_workflow_only)}
              onChange={(e) => updateFilter("used_in_workflow_only", e.target.checked)}
            />
            used in current workflow only
          </label>
          <button
            onClick={applyFilters}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10"
          >
            Apply filters
          </button>
        </div>
      </div>

      {loading ? (
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">Loading Agent Registry...</div>
      ) : error ? (
        <div className="glass-panel p-6 text-sm font-mono text-ork-red">{error}</div>
      ) : agents.length === 0 ? (
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-dim">No agents found.</div>
      ) : (
        <div className="glass-panel overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead className="border-b border-ork-border/60 text-ork-dim bg-ork-panel/60">
              <tr>
                <th className="p-3 text-left">name</th>
                <th className="p-3 text-left">agent_id</th>
                <th className="p-3 text-left">family</th>
                <th className="p-3 text-left">purpose</th>
                <th className="p-3 text-left">skills</th>
                <th className="p-3 text-left">allowed_mcps</th>
                <th className="p-3 text-left">criticality</th>
                <th className="p-3 text-left">cost_profile</th>
                <th className="p-3 text-left">version</th>
                <th className="p-3 text-left">status</th>
                <th className="p-3 text-left">last test</th>
                <th className="p-3 text-left">actions</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((agent) => (
                <tr key={agent.id} className="border-b border-ork-border/40 align-top">
                  <td className="p-3 text-ork-text font-semibold">{agent.name}</td>
                  <td className="p-3 text-ork-cyan">{agent.id}</td>
                  <td className="p-3">{agent.family?.label || agent.family_id}</td>
                  <td className="p-3 max-w-[280px] text-ork-muted">{agent.purpose}</td>
                  <td className="p-3">{(agent.skill_ids ?? []).slice(0, 3).join(", ") || "-"}</td>
                  <td className="p-3">{agent.allowed_mcps?.length ?? 0}</td>
                  <td className="p-3">{agent.criticality}</td>
                  <td className="p-3">{agent.cost_profile}</td>
                  <td className="p-3">{agent.version}</td>
                  <td className="p-3">
                    <StatusBadge status={agent.status} />
                  </td>
                  <td className="p-3">
                    <StatusBadge status={agent.last_test_status || "not_tested"} />
                  </td>
                  <td className="p-3 space-y-1">
                    <Link href={`/agents/${agent.id}`} className="text-ork-cyan hover:underline block">
                      View details
                    </Link>
                    <Link href={`/agents/${agent.id}/edit`} className="text-ork-purple hover:underline block">
                      Edit
                    </Link>
                    <button
                      onClick={() => void openAgentHistory(agent)}
                      className="text-ork-cyan hover:underline block"
                    >
                      History
                    </button>
                    <button
                      onClick={() => setAgentPendingDelete(agent)}
                      disabled={deletingAgentId === agent.id}
                      className="text-ork-red hover:underline block disabled:opacity-50"
                    >
                      {deletingAgentId === agent.id ? "Deleting..." : "Delete"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

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
