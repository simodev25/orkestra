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
        setAgents(a);
        setMcps(mc);
      } catch (err: any) {
        setError(err.message || "Failed to load metrics");
        setMetrics(MOCK_METRICS);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const isDemo = !!error;
  const activeAgents = isDemo ? 6 : agents.filter((a) => a.status === "active").length;
  const activeMcps = isDemo ? 4 : mcps.filter((m) => m.status === "active").length;
  const m = metrics || MOCK_METRICS;

  const maxStatusCount = Math.max(...Object.values(m.runs_by_status), 1);

  const statusBarColor: Record<string, string> = {
    completed: "bg-ork-green",
    running: "bg-ork-cyan",
    failed: "bg-ork-red",
    planned: "bg-ork-purple",
    pending: "bg-ork-amber",
    cancelled: "bg-ork-dim",
    blocked: "bg-ork-red/60",
  };

  const decisionColor: Record<string, string> = {
    allow: "text-ork-green",
    deny: "text-ork-red",
    review_required: "text-ork-amber",
    adjust: "text-ork-purple",
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin mx-auto" />
          <p className="data-label">LOADING PLATFORM METRICS...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title text-sm mb-1">ORKESTRA &mdash; COMMAND CENTER</h1>
          <p className="text-ork-dim text-xs font-mono">
            Governed Multi-Agent Orchestration Platform
          </p>
        </div>
        {error && (
          <span className="text-[10px] font-mono text-ork-amber bg-ork-amber/10 border border-ork-amber/20 rounded px-2 py-1">
            DEMO MODE &mdash; API OFFLINE
          </span>
        )}
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="TOTAL RUNS"
          value={m.total_runs}
          sub={`${m.runs_by_status.running || 0} active`}
          accent="cyan"
        />
        <StatCard
          label="ACTIVE AGENTS"
          value={activeAgents}
          sub={`${agents.length || 8} registered`}
          accent="green"
        />
        <StatCard
          label="ACTIVE MCPs"
          value={activeMcps}
          sub={`${mcps.length || 6} registered`}
          accent="purple"
        />
        <StatCard
          label="TOTAL COST"
          value={`$${m.total_cost.toFixed(2)}`}
          sub={`agents $${m.total_agent_cost.toFixed(2)} / mcps $${m.total_mcp_cost.toFixed(2)}`}
          accent="amber"
        />
      </div>

      {/* Middle row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Runs by Status */}
        <div className="glass-panel p-5">
          <h2 className="section-title mb-4">RUNS BY STATUS</h2>
          <div className="space-y-3">
            {Object.entries(m.runs_by_status).map(([status, count]) => (
              <div key={status} className="flex items-center gap-3">
                <div className="w-24 shrink-0">
                  <StatusBadge status={status} />
                </div>
                <div className="flex-1 h-5 bg-ork-bg rounded overflow-hidden">
                  <div
                    className={`h-full rounded transition-all duration-500 ${statusBarColor[status] || "bg-ork-dim"}`}
                    style={{ width: `${(count / maxStatusCount) * 100}%`, minWidth: count > 0 ? "8px" : "0" }}
                  />
                </div>
                <span className="font-mono text-sm text-ork-text w-8 text-right">{count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Control Decisions */}
        <div className="glass-panel p-5">
          <h2 className="section-title mb-4">CONTROL DECISIONS</h2>
          <div className="grid grid-cols-2 gap-4">
            {Object.entries(m.control_decisions_by_type).map(([type, count]) => (
              <div key={type} className="bg-ork-bg rounded-lg p-3 border border-ork-border/50">
                <p className="data-label mb-1">{type.replace(/_/g, " ").toUpperCase()}</p>
                <p className={`text-xl font-mono font-semibold ${decisionColor[type] || "text-ork-text"}`}>
                  {count}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t border-ork-border/50 flex items-center justify-between">
            <span className="data-label">TOTAL DECISIONS</span>
            <span className="font-mono text-sm text-ork-text">
              {Object.values(m.control_decisions_by_type).reduce((a, b) => a + b, 0)}
            </span>
          </div>
        </div>
      </div>

      {/* Audit Events + Quick Links */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="glass-panel p-5">
          <h2 className="section-title mb-3">AUDIT TRAIL</h2>
          <p className="stat-value text-ork-cyan">{m.audit_events_total}</p>
          <p className="text-xs text-ork-dim mt-1 font-mono">total recorded events</p>
        </div>

        <div className="glass-panel p-5 lg:col-span-2">
          <h2 className="section-title mb-3">QUICK ACTIONS</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { href: "/requests/new", label: "NEW REQUEST", color: "border-ork-cyan/30 hover:border-ork-cyan/60 text-ork-cyan" },
              { href: "/requests", label: "REQUESTS", color: "border-ork-green/30 hover:border-ork-green/60 text-ork-green" },
              { href: "/cases", label: "CASES", color: "border-ork-purple/30 hover:border-ork-purple/60 text-ork-purple" },
              { href: "/runs", label: "RUNS", color: "border-ork-amber/30 hover:border-ork-amber/60 text-ork-amber" },
            ].map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={`block text-center py-3 px-2 rounded-lg border bg-ork-bg transition-colors duration-200 font-mono text-[11px] tracking-wider ${link.color}`}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
