"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { Case } from "@/lib/types";

const STATUS_FILTERS = [
  "all",
  "ready_for_planning",
  "planning",
  "running",
  "completed",
  "failed",
] as const;

export default function CasesPage() {
  const [cases, setCases] = useState<Case[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.listCases(filter === "all" ? undefined : filter);
        setCases(data);
      } catch (err: any) {
        setError(err.message || "Failed to load cases");
        setCases([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [filter]);

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title text-sm mb-1">CASES</h1>
          <p className="text-ork-dim text-xs font-mono">
            Active orchestration cases and their execution state
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="data-label mr-1">FILTER:</span>
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 text-[10px] font-mono uppercase tracking-wider rounded border transition-colors duration-200 ${
              filter === s
                ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                : "bg-ork-bg text-ork-dim border-ork-border hover:border-ork-dim"
            }`}
          >
            {s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="glass-panel p-3 border-ork-amber/30">
          <p className="text-xs font-mono text-ork-amber">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="text-center space-y-3">
            <div className="w-6 h-6 border-2 border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin mx-auto" />
            <p className="data-label">LOADING CASES...</p>
          </div>
        </div>
      )}

      {/* Table */}
      {!loading && cases.length > 0 && (
        <div className="glass-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-ork-border">
                  <th className="text-left data-label px-4 py-3">ID</th>
                  <th className="text-left data-label px-4 py-3">REQUEST ID</th>
                  <th className="text-left data-label px-4 py-3">TYPE</th>
                  <th className="text-left data-label px-4 py-3">CRITICALITY</th>
                  <th className="text-left data-label px-4 py-3">STATUS</th>
                  <th className="text-left data-label px-4 py-3">RUN ID</th>
                  <th className="text-left data-label px-4 py-3">CREATED</th>
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-ork-border/50 hover:bg-ork-panel/50 transition-colors duration-150 group cursor-pointer"
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-ork-cyan group-hover:text-ork-cyan/80">
                        {c.id.slice(0, 8)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-ork-muted">
                        {c.request_id.slice(0, 8)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-ork-text">
                        {c.case_type || "--"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={c.criticality} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="px-4 py-3">
                      {c.current_run_id ? (
                        <Link
                          href={`/runs/${c.current_run_id}`}
                          className="font-mono text-xs text-ork-green hover:text-ork-green/80 underline underline-offset-2 decoration-ork-green/30"
                          onClick={(e) => e.stopPropagation()}
                        >
                          {c.current_run_id.slice(0, 8)}
                        </Link>
                      ) : (
                        <span className="font-mono text-xs text-ork-dim">--</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-ork-dim">
                        {formatDate(c.created_at)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && cases.length === 0 && !error && (
        <div className="glass-panel p-12 text-center">
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-full border-2 border-ork-border mx-auto flex items-center justify-center">
              <span className="text-ork-dim text-lg">0</span>
            </div>
            <p className="text-sm text-ork-muted">No cases found</p>
            <p className="text-xs text-ork-dim font-mono">
              {filter !== "all"
                ? `No cases with status "${filter.replace(/_/g, " ")}"`
                : "Cases are created when requests are processed"}
            </p>
            <Link
              href="/requests/new"
              className="inline-block mt-2 px-4 py-2 bg-ork-cyan/10 border border-ork-cyan/30 rounded-lg text-ork-cyan text-xs font-mono uppercase tracking-wider hover:bg-ork-cyan/20 transition-colors"
            >
              + Create a Request
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
