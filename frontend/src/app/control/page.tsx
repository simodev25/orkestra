"use client";

import { useState, useEffect } from "react";
import { StatusBadge } from "@/components/ui/status-badge";
import { StatCard } from "@/components/ui/stat-card";
import { api } from "@/lib/api";
import type { ControlDecision } from "@/lib/types";

const SCOPES = ["all", "plan", "agent", "mcp"] as const;
const TYPES = ["all", "allow", "deny", "hold", "review_required"] as const;

export default function ControlDecisionsPage() {
  const [decisions, setDecisions] = useState<ControlDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scopeFilter, setScopeFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  useEffect(() => {
    async function load() {
      try {
        const data = await api.listControlDecisions();
        setDecisions(data);
      } catch (err: any) {
        setError(err.message || "Failed to load control decisions");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = decisions.filter((d) => {
    if (scopeFilter !== "all" && d.decision_scope !== scopeFilter) return false;
    if (typeFilter !== "all" && d.decision_type !== typeFilter) return false;
    return true;
  });

  const totalDecisions = decisions.length;
  const allows = decisions.filter((d) => d.decision_type === "allow").length;
  const denials = decisions.filter((d) => d.decision_type === "deny").length;
  const reviews = decisions.filter((d) => d.decision_type === "review_required").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin mx-auto" />
          <p className="data-label">LOADING CONTROL DECISIONS...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title text-sm mb-1">CONTROL DECISIONS</h1>
          <p className="text-ork-dim text-xs font-mono">
            Real-time governance enforcement across all execution scopes
          </p>
        </div>
        {error && (
          <span className="text-[10px] font-mono text-ork-amber bg-ork-amber/10 border border-ork-amber/20 rounded px-2 py-1">
            {error}
          </span>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="TOTAL DECISIONS" value={totalDecisions} accent="cyan" />
        <StatCard label="ALLOWS" value={allows} accent="green" />
        <StatCard label="DENIALS" value={denials} accent="red" />
        <StatCard label="REVIEWS REQUIRED" value={reviews} accent="amber" />
      </div>

      {/* Filters */}
      <div className="glass-panel p-4 flex flex-wrap items-center gap-6">
        <div className="flex items-center gap-2">
          <span className="data-label">SCOPE</span>
          <div className="flex gap-1">
            {SCOPES.map((s) => (
              <button
                key={s}
                onClick={() => setScopeFilter(s)}
                className={`px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider rounded border transition-colors duration-150 ${
                  scopeFilter === s
                    ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                    : "border-ork-border text-ork-muted hover:text-ork-text hover:border-ork-dim"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="data-label">TYPE</span>
          <div className="flex gap-1">
            {TYPES.map((t) => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={`px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider rounded border transition-colors duration-150 ${
                  typeFilter === t
                    ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                    : "border-ork-border text-ork-muted hover:text-ork-text hover:border-ork-dim"
                }`}
              >
                {t.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>
        <span className="ml-auto data-label">
          {filtered.length} of {totalDecisions} shown
        </span>
      </div>

      {/* Table */}
      <div className="glass-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-ork-border">
                {["ID", "RUN ID", "SCOPE", "TYPE", "REASON", "SEVERITY", "TARGET", "TIME"].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-[10px] font-mono uppercase tracking-wider text-ork-dim font-medium"
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-ork-border/50">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center">
                    <p className="text-ork-muted text-sm">No control decisions found</p>
                    <p className="text-ork-dim text-xs font-mono mt-1">
                      Decisions will appear here when governance rules are evaluated during runs
                    </p>
                  </td>
                </tr>
              ) : (
                filtered.map((d) => (
                  <tr
                    key={d.id}
                    className="hover:bg-ork-hover/50 transition-colors duration-100"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-ork-muted">
                      {d.id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-ork-cyan">
                      {d.run_id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider bg-ork-purple/10 text-ork-purple border border-ork-purple/20 rounded">
                        {d.decision_scope}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={d.decision_type} />
                    </td>
                    <td className="px-4 py-3 text-xs text-ork-text max-w-[200px] truncate">
                      {d.reason}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`font-mono text-xs ${
                          d.severity === "critical"
                            ? "text-ork-red"
                            : d.severity === "high"
                            ? "text-ork-amber"
                            : d.severity === "medium"
                            ? "text-ork-purple"
                            : "text-ork-muted"
                        }`}
                      >
                        {d.severity}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-ork-dim">
                      {d.target_ref ? d.target_ref.slice(0, 12) : "\u2014"}
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-ork-dim whitespace-nowrap">
                      {new Date(d.created_at).toLocaleString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
