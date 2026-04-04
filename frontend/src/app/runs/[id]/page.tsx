"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { StatCard } from "@/components/ui/stat-card";
import { api } from "@/lib/api";
import type { Run, RunNode, RunLiveState, ControlDecision } from "@/lib/types";

const NODE_DOT_COLORS: Record<string, string> = {
  running: "bg-ork-cyan",
  completed: "bg-ork-green",
  pending: "bg-ork-amber",
  ready: "bg-ork-amber",
  failed: "bg-ork-red",
  blocked: "bg-ork-red",
  cancelled: "bg-ork-dim",
  planned: "bg-ork-purple",
};

const NODE_LINE_COLORS: Record<string, string> = {
  running: "border-ork-cyan/40",
  completed: "border-ork-green/30",
  pending: "border-ork-amber/20",
  ready: "border-ork-amber/20",
  failed: "border-ork-red/30",
  blocked: "border-ork-red/20",
  cancelled: "border-ork-border",
  planned: "border-ork-purple/20",
};

export default function RunDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [run, setRun] = useState<Run | null>(null);
  const [nodes, setNodes] = useState<RunNode[]>([]);
  const [liveState, setLiveState] = useState<RunLiveState | null>(null);
  const [decisions, setDecisions] = useState<ControlDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const fetchData = useCallback(() => {
    if (!id) return;
    Promise.all([
      api.getRun(id),
      api.getRunNodes(id),
      api.getRunLiveState(id),
      api.getRunControlDecisions(id),
    ])
      .then(([runData, nodesData, liveData, decisionsData]) => {
        setRun(runData);
        setNodes(nodesData);
        setLiveState(liveData);
        setDecisions(decisionsData);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  async function handleStart() {
    if (!id) return;
    setActionLoading(true);
    try {
      const updated = await api.startRun(id);
      setRun(updated);
      fetchData();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleCancel() {
    if (!id) return;
    setActionLoading(true);
    try {
      const updated = await api.cancelRun(id);
      setRun(updated);
      fetchData();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setActionLoading(false);
    }
  }

  function formatCost(v: number | null | undefined) {
    if (v == null) return "--";
    return `$${v.toFixed(2)}`;
  }

  function formatDate(iso: string | null) {
    if (!iso) return "--";
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  }

  const sortedNodes = [...nodes].sort((a, b) => a.order_index - b.order_index);

  // Group nodes by parallel_group for visual clustering
  const groupedNodes: { group: string | null; items: RunNode[] }[] = [];
  for (const node of sortedNodes) {
    const lastGroup = groupedNodes[groupedNodes.length - 1];
    if (lastGroup && lastGroup.group === node.parallel_group && node.parallel_group !== null) {
      lastGroup.items.push(node);
    } else {
      groupedNodes.push({ group: node.parallel_group, items: [node] });
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-16 text-center">
          <div className="text-ork-cyan font-mono text-sm animate-pulse">
            Loading run data...
          </div>
        </div>
      </div>
    );
  }

  if (error && !run) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-8 text-center">
          <p className="text-ork-red font-mono text-sm">Error: {error}</p>
          <Link href="/runs" className="text-ork-cyan text-xs font-mono mt-3 inline-block hover:underline">
            Back to runs
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/runs"
            className="text-ork-muted hover:text-ork-cyan transition-colors text-xs font-mono"
          >
            RUNS /
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="font-mono text-sm tracking-wide text-ork-text">
                {id?.slice(0, 12)}...
              </h1>
              {run && <StatusBadge status={run.status} />}
            </div>
            <p className="text-[10px] text-ork-dim font-mono mt-0.5">
              Case {run?.case_id.slice(0, 8)} &middot; Plan {run?.plan_id.slice(0, 8)}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          {run?.status === "planned" && (
            <button
              onClick={handleStart}
              disabled={actionLoading}
              className="px-4 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-cyan/15 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/25 transition-colors disabled:opacity-50"
            >
              {actionLoading ? "Starting..." : "Start Run"}
            </button>
          )}
          {run?.status === "running" && (
            <button
              onClick={handleCancel}
              disabled={actionLoading}
              className="px-4 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-red/15 text-ork-red border border-ork-red/30 rounded hover:bg-ork-red/25 transition-colors disabled:opacity-50"
            >
              {actionLoading ? "Cancelling..." : "Cancel Run"}
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="glass-panel p-3 border-ork-red/30 bg-ork-red/5">
          <p className="text-ork-red text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Stat Cards */}
      <div className="grid grid-cols-4 gap-4">
        <StatCard
          label="STATUS"
          value={run?.status?.toUpperCase() || "--"}
          sub={run?.started_at ? `Since ${formatDate(run.started_at)}` : undefined}
          accent={
            run?.status === "running"
              ? "cyan"
              : run?.status === "completed"
              ? "green"
              : run?.status === "failed"
              ? "red"
              : "purple"
          }
        />
        <StatCard
          label="EST. COST"
          value={formatCost(liveState?.estimated_cost ?? run?.estimated_cost)}
          accent="amber"
        />
        <StatCard
          label="ACTUAL COST"
          value={formatCost(liveState?.actual_cost ?? run?.actual_cost)}
          sub={
            liveState
              ? `Agents: ${formatCost(liveState.agent_invocations_cost)} / MCPs: ${formatCost(liveState.mcp_invocations_cost)}`
              : undefined
          }
          accent="green"
        />
        <StatCard
          label="NODES TOTAL"
          value={liveState?.nodes_total ?? nodes.length}
          sub={
            liveState?.nodes_by_status
              ? Object.entries(liveState.nodes_by_status)
                  .map(([k, v]) => `${v} ${k}`)
                  .join(", ")
              : undefined
          }
          accent="cyan"
        />
      </div>

      {/* Live Metrics */}
      {liveState && (
        <div className="grid grid-cols-4 gap-4">
          <div className="glass-panel p-3">
            <p className="data-label">Agent Invocations</p>
            <p className="font-mono text-sm text-ork-text mt-1">{liveState.agent_invocations}</p>
          </div>
          <div className="glass-panel p-3">
            <p className="data-label">MCP Invocations</p>
            <p className="font-mono text-sm text-ork-text mt-1">{liveState.mcp_invocations}</p>
          </div>
          <div className="glass-panel p-3">
            <p className="data-label">Control Decisions</p>
            <p className="font-mono text-sm text-ork-text mt-1">{liveState.control_decisions}</p>
          </div>
          <div className="glass-panel p-3">
            <p className="data-label">Denials</p>
            <p className="font-mono text-sm text-ork-red mt-1">{liveState.control_denials}</p>
          </div>
        </div>
      )}

      {/* Execution Graph */}
      <div>
        <h2 className="section-title mb-4">Execution Graph</h2>
        <div className="glass-panel p-6">
          {sortedNodes.length === 0 ? (
            <p className="text-ork-muted font-mono text-xs text-center py-8">
              No execution nodes
            </p>
          ) : (
            <div className="space-y-0">
              {groupedNodes.map((group, gi) => (
                <div key={gi}>
                  {/* Connector line from previous group */}
                  {gi > 0 && (
                    <div className="flex justify-center">
                      <div className="w-px h-6 border-l-2 border-dashed border-ork-border" />
                    </div>
                  )}

                  {/* Parallel group label */}
                  {group.group && (
                    <div className="flex items-center gap-2 mb-2 ml-8">
                      <span className="text-[9px] font-mono uppercase tracking-widest text-ork-purple bg-ork-purple/10 border border-ork-purple/20 px-2 py-0.5 rounded">
                        parallel: {group.group}
                      </span>
                    </div>
                  )}

                  {/* Nodes in this group */}
                  <div className={group.items.length > 1 ? "flex gap-3 flex-wrap" : ""}>
                    {group.items.map((node, ni) => {
                      const dotColor = NODE_DOT_COLORS[node.status] || "bg-ork-dim";
                      const lineColor = NODE_LINE_COLORS[node.status] || "border-ork-border";

                      return (
                        <div
                          key={node.id}
                          className={`flex items-start gap-3 ${
                            group.items.length > 1 ? "flex-1 min-w-[220px]" : ""
                          }`}
                        >
                          {/* Vertical connector + dot */}
                          <div className="flex flex-col items-center pt-1">
                            <div
                              className={`w-2.5 h-2.5 rounded-full ${dotColor} ${
                                node.status === "running" ? "animate-pulse" : ""
                              }`}
                              style={{
                                boxShadow:
                                  node.status === "running"
                                    ? "0 0 10px rgba(0,212,255,0.5)"
                                    : node.status === "completed"
                                    ? "0 0 6px rgba(0,255,136,0.3)"
                                    : node.status === "failed"
                                    ? "0 0 6px rgba(255,68,68,0.4)"
                                    : "none",
                              }}
                            />
                            {/* Vertical line to next node (only in sequential mode) */}
                            {group.items.length === 1 &&
                              gi < groupedNodes.length - 1 && (
                                <div className={`w-px flex-1 min-h-[24px] border-l-2 ${lineColor}`} />
                              )}
                          </div>

                          {/* Node card */}
                          <div
                            className={`flex-1 glass-panel p-3 mb-2 border-l-2 ${lineColor}`}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className="font-mono text-xs text-ork-text font-medium">
                                {node.node_ref}
                              </span>
                              <StatusBadge status={node.status} />
                            </div>
                            <div className="flex items-center gap-3 text-[10px] font-mono text-ork-dim">
                              <span>type: {node.node_type}</span>
                              <span>order: {node.order_index}</span>
                              {node.started_at && (
                                <span>started: {formatDate(node.started_at)}</span>
                              )}
                              {node.ended_at && (
                                <span>ended: {formatDate(node.ended_at)}</span>
                              )}
                            </div>
                            {node.depends_on && node.depends_on.length > 0 && (
                              <div className="mt-1.5 flex items-center gap-1.5">
                                <span className="text-[9px] font-mono text-ork-dim">deps:</span>
                                {node.depends_on.map((dep) => (
                                  <span
                                    key={dep}
                                    className="text-[9px] font-mono text-ork-muted bg-ork-panel px-1.5 py-0.5 rounded border border-ork-border"
                                  >
                                    {dep.slice(0, 8)}
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Control Decisions */}
      {decisions.length > 0 && (
        <div>
          <h2 className="section-title mb-4">Control Decisions</h2>
          <div className="glass-panel overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ork-border">
                  <th className="data-label text-left px-4 py-2.5">Type</th>
                  <th className="data-label text-left px-4 py-2.5">Scope</th>
                  <th className="data-label text-left px-4 py-2.5">Severity</th>
                  <th className="data-label text-left px-4 py-2.5">Target</th>
                  <th className="data-label text-left px-4 py-2.5">Reason</th>
                  <th className="data-label text-left px-4 py-2.5">Time</th>
                </tr>
              </thead>
              <tbody>
                {decisions.map((d) => (
                  <tr
                    key={d.id}
                    className="border-b border-ork-border/50"
                  >
                    <td className="px-4 py-2.5">
                      <StatusBadge status={d.decision_type} />
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-muted">
                      {d.decision_scope}
                    </td>
                    <td className="px-4 py-2.5">
                      <span
                        className={`font-mono uppercase text-[10px] ${
                          d.severity === "critical"
                            ? "text-ork-red"
                            : d.severity === "high"
                            ? "text-ork-amber"
                            : "text-ork-muted"
                        }`}
                      >
                        {d.severity}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-dim">
                      {d.target_ref || "--"}
                    </td>
                    <td className="px-4 py-2.5 text-ork-muted max-w-[300px] truncate">
                      {d.reason}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-dim">
                      {formatDate(d.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
