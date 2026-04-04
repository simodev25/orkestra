"use client";

import { useState, useEffect } from "react";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { MCP } from "@/lib/types";

const EFFECT_COLORS: Record<string, string> = {
  read: "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/25",
  compute: "bg-ork-purple/15 text-ork-purple border-ork-purple/25",
  write: "bg-ork-amber/15 text-ork-amber border-ork-amber/25",
  act: "bg-ork-red/15 text-ork-red border-ork-red/25",
  observe: "bg-ork-green/15 text-ork-green border-ork-green/25",
  transform: "bg-ork-purple/15 text-ork-purple border-ork-purple/25",
};

const EFFECT_DEFAULT = "bg-ork-dim/20 text-ork-muted border-ork-dim/30";

const STATUS_OPTIONS = ["all", "active", "registered", "tested", "deprecated", "disabled", "archived"];

export default function MCPsPage() {
  const [mcps, setMcps] = useState<MCP[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .listMCPs()
      .then(setMcps)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const effectTypes = ["all", ...Array.from(new Set(mcps.map((m) => m.effect_type)))];
  const [effectFilter, setEffectFilter] = useState("all");

  const filtered = mcps.filter((m) => {
    if (statusFilter !== "all" && m.status !== statusFilter) return false;
    if (effectFilter !== "all" && m.effect_type !== effectFilter) return false;
    return true;
  });

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-wide">MCP REGISTRY</h1>
          <p className="text-xs text-ork-dim font-mono mt-0.5">
            Model Context Protocols and tool capabilities
          </p>
        </div>
        <div className="text-xs font-mono text-ork-dim">
          {filtered.length} MCP{filtered.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div>
          <span className="data-label mr-2">Effect</span>
          <div className="inline-flex gap-1 flex-wrap">
            {effectTypes.map((e) => (
              <button
                key={e}
                onClick={() => setEffectFilter(e)}
                className={`px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider rounded border transition-colors duration-150 ${
                  effectFilter === e
                    ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                    : "bg-ork-surface text-ork-muted border-ork-border hover:border-ork-cyan/20 hover:text-ork-text"
                }`}
              >
                {e}
              </button>
            ))}
          </div>
        </div>
        <div>
          <span className="data-label mr-2">Status</span>
          <div className="inline-flex gap-1 flex-wrap">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider rounded border transition-colors duration-150 ${
                  statusFilter === s
                    ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                    : "bg-ork-surface text-ork-muted border-ork-border hover:border-ork-cyan/20 hover:text-ork-text"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="glass-panel p-12 text-center">
          <div className="text-ork-cyan font-mono text-sm animate-pulse">
            Loading MCPs...
          </div>
        </div>
      ) : error ? (
        <div className="glass-panel p-8 text-center">
          <p className="text-ork-red font-mono text-sm">Error: {error}</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <p className="text-ork-muted font-mono text-sm">No MCPs found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((mcp) => (
            <div
              key={mcp.id}
              className="glass-panel-hover p-4 flex flex-col gap-3"
            >
              {/* Name + ID */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-sm font-semibold text-ork-text">
                    {mcp.name}
                  </h3>
                  <StatusBadge status={mcp.status} />
                </div>
                <p className="font-mono text-[10px] text-ork-dim">
                  {mcp.id}
                </p>
              </div>

              {/* Effect Type Tag */}
              <div className="flex items-center gap-2">
                <span
                  className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${
                    EFFECT_COLORS[mcp.effect_type] || EFFECT_DEFAULT
                  }`}
                >
                  {mcp.effect_type}
                </span>
                {mcp.approval_required && (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-ork-amber bg-ork-amber/10 border border-ork-amber/20 rounded">
                    <svg
                      className="w-2.5 h-2.5"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                    approval
                  </span>
                )}
              </div>

              {/* Purpose */}
              <p className="text-xs text-ork-muted leading-relaxed line-clamp-2">
                {mcp.purpose}
              </p>

              {/* Meta row */}
              <div className="flex items-center gap-3 text-[10px] font-mono text-ork-dim border-t border-ork-border pt-3 mt-auto">
                <span>
                  crit:{" "}
                  <span
                    className={
                      mcp.criticality === "critical"
                        ? "text-ork-red"
                        : mcp.criticality === "high"
                        ? "text-ork-amber"
                        : "text-ork-muted"
                    }
                  >
                    {mcp.criticality}
                  </span>
                </span>
                <span className="text-ork-border">|</span>
                <span>
                  timeout:{" "}
                  <span className="text-ork-muted">{mcp.timeout_seconds}s</span>
                </span>
                <span className="text-ork-border">|</span>
                <span>
                  cost: <span className="text-ork-muted">{mcp.cost_profile}</span>
                </span>
              </div>

              {/* Allowed Agents */}
              <div className="text-[10px] font-mono text-ork-dim">
                <span className="text-ork-muted">
                  {mcp.allowed_agents?.length ?? 0}
                </span>{" "}
                allowed agents
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
