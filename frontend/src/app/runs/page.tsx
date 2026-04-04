"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";

const STATUS_OPTIONS = ["all", "planned", "running", "completed", "failed", "cancelled", "blocked"];

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .listRuns()
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered =
    statusFilter === "all" ? runs : runs.filter((r) => r.status === statusFilter);

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
      hour12: false,
    });
  }

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-wide">RUNS</h1>
          <p className="text-xs text-ork-dim font-mono mt-0.5">
            Execution instances across all cases
          </p>
        </div>
        <div className="text-xs font-mono text-ork-dim">
          {filtered.length} run{filtered.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-1.5">
        {STATUS_OPTIONS.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1 text-[11px] font-mono uppercase tracking-wider rounded border transition-colors duration-150 ${
              statusFilter === s
                ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                : "bg-ork-surface text-ork-muted border-ork-border hover:border-ork-cyan/20 hover:text-ork-text"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="glass-panel p-12 text-center">
          <div className="text-ork-cyan font-mono text-sm animate-pulse">
            Loading runs...
          </div>
        </div>
      ) : error ? (
        <div className="glass-panel p-8 text-center">
          <p className="text-ork-red font-mono text-sm">Error: {error}</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <p className="text-ork-muted font-mono text-sm">No runs found</p>
        </div>
      ) : (
        <div className="glass-panel overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ork-border">
                <th className="data-label text-left px-4 py-3">Run ID</th>
                <th className="data-label text-left px-4 py-3">Case ID</th>
                <th className="data-label text-left px-4 py-3">Plan ID</th>
                <th className="data-label text-left px-4 py-3">Status</th>
                <th className="data-label text-right px-4 py-3">Est. Cost</th>
                <th className="data-label text-right px-4 py-3">Actual Cost</th>
                <th className="data-label text-left px-4 py-3">Started At</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => (
                <tr
                  key={run.id}
                  className="border-b border-ork-border/50 hover:bg-ork-cyan/[0.03] transition-colors duration-100"
                >
                  <td className="px-4 py-3">
                    <Link
                      href={`/runs/${run.id}`}
                      className="font-mono text-xs text-ork-cyan hover:underline"
                    >
                      {run.id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ork-muted">
                    {run.case_id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ork-muted">
                    {run.plan_id.slice(0, 8)}...
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={run.status} />
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-right text-ork-muted">
                    {formatCost(run.estimated_cost)}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-right text-ork-text">
                    {formatCost(run.actual_cost)}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-ork-dim">
                    {formatDate(run.started_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
