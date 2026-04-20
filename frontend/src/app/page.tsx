"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { StatCard } from "@/components/ui/stat-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { PlatformMetrics, Agent, MCP } from "@/lib/types";

const MOCK_METRICS: PlatformMetrics = {
  total_runs: 24,
  runs_by_status: { completed: 14, running: 3, failed: 2, planned: 5 },
  total_agent_cost: 12.48,
  total_mcp_cost: 3.72,
  total_cost: 16.2,
  control_decisions_by_type: { allow: 42, deny: 7, review_required: 5, adjust: 3 },
  audit_events_total: 187,
};

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<PlatformMetrics | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [mcps, setMcps] = useState<MCP[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [m, a, mc] = await Promise.all([
          api.getPlatformMetrics(),
          api.listAgents(),
          api.listMCPs(),
        ]);
        setMetrics(m);
        setAgents(a.items || []);
        setMcps(mc.items || []);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "API offline");
        setMetrics(MOCK_METRICS);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const m = metrics || MOCK_METRICS;
  const activeAgents = error ? 6 : agents.filter((a) => a.status === "active").length;
  const activeMcps = error ? 4 : mcps.filter((mc) => mc.status === "active").length;
  const maxStatusCount = Math.max(...Object.values(m.runs_by_status), 1);

  const statusBarColor: Record<string, string> = {
    completed: "var(--ork-green)", running: "var(--ork-cyan)",
    failed: "var(--ork-red)", planned: "var(--ork-purple)",
    pending: "var(--ork-amber)", cancelled: "var(--ork-muted-2)",
    blocked: "var(--ork-red)",
  };

  const decisionColor: Record<string, string> = {
    allow: "var(--ork-green)", deny: "var(--ork-red)",
    review_required: "var(--ork-amber)", adjust: "var(--ork-purple)",
  };

  if (loading) {
    return (
      <div className="page" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
          <div style={{ width: 24, height: 24, border: "2px solid var(--ork-border)", borderTopColor: "var(--ork-cyan)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
          <p className="section-title">Loading platform metrics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page animate-fade-in">
      {/* Page header */}
      <div className="pagehead">
        <div>
          <h1>Command Center</h1>
          <p>Governed Multi-Agent Orchestration Platform</p>
        </div>
        {error && (
          <span className="badge badge--pending">demo mode · api offline</span>
        )}
      </div>

      {/* Stat cards */}
      <div className="stats">
        <StatCard label="Total Runs"     value={m.total_runs}                          accent="cyan"   barPercent={75} sub={`${m.runs_by_status.running || 0} active`} />
        <StatCard label="Active Agents"  value={activeAgents}                          accent="green"  barPercent={Math.round((activeAgents / (agents.length || 8)) * 100)} sub={`${agents.length || 8} registered`} />
        <StatCard label="Active MCPs"    value={activeMcps}                            accent="purple" barPercent={Math.round((activeMcps / (mcps.length || 6)) * 100)} sub={`${mcps.length || 6} registered`} />
        <StatCard label="Total Cost"     value={`$${m.total_cost.toFixed(2)}`}         accent="amber"  sub={`agents $${m.total_agent_cost.toFixed(2)}`} />
      </div>

      {/* Middle row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 12 }}>
        {/* Runs by Status */}
        <div className="glass-panel" style={{ padding: "14px 16px" }}>
          <p className="section-title" style={{ marginBottom: 12 }}>Runs by Status</p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {Object.entries(m.runs_by_status).map(([status, count]) => (
              <div key={status} className="row">
                <div style={{ width: 90, flexShrink: 0 }}>
                  <StatusBadge status={status} />
                </div>
                <div style={{ flex: 1, height: 4, background: "var(--ork-border)", borderRadius: 999, overflow: "hidden" }}>
                  <div style={{ height: "100%", borderRadius: 999, background: statusBarColor[status] || "var(--ork-muted-2)", width: `${(count / maxStatusCount) * 100}%`, minWidth: count > 0 ? 4 : 0 }} />
                </div>
                <span className="mono dim" style={{ fontSize: 12, width: 28, textAlign: "right" }}>{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Control Decisions */}
        <div className="glass-panel" style={{ padding: "14px 16px" }}>
          <p className="section-title" style={{ marginBottom: 12 }}>Control Decisions</p>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            {Object.entries(m.control_decisions_by_type).map(([type, count]) => (
              <div key={type} style={{ background: "var(--ork-bg)", borderRadius: "var(--radius-lg)", padding: "10px 12px", border: "1px solid var(--ork-border)" }}>
                <p className="section-title" style={{ marginBottom: 6 }}>{type.replace(/_/g, " ")}</p>
                <p className="stat-value" style={{ color: decisionColor[type] || "var(--ork-text)" }}>{count}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Bottom row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: 12 }}>
        <div className="glass-panel" style={{ padding: "14px 16px" }}>
          <p className="section-title" style={{ marginBottom: 8 }}>Audit Trail</p>
          <p className="stat-value" style={{ color: "var(--ork-cyan)" }}>{m.audit_events_total}</p>
          <p className="dim" style={{ fontFamily: "var(--font-mono)", fontSize: 11, marginTop: 4 }}>total recorded events</p>
        </div>
        <div className="glass-panel" style={{ padding: "14px 16px" }}>
          <p className="section-title" style={{ marginBottom: 10 }}>Quick Actions</p>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Link href="/requests/new" className="btn btn--cyan">New Request</Link>
            <Link href="/agents/new"   className="btn">New Agent</Link>
            <Link href="/approvals"    className="btn">Approvals</Link>
            <Link href="/requests"     className="btn">Requests</Link>
            <Link href="/runs"         className="btn">Runs</Link>
          </div>
        </div>
      </div>
    </div>
  );
}
