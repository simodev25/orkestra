"use client";

import { useState, useEffect } from "react";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { Agent } from "@/lib/types";

const FAMILY_COLORS: Record<string, string> = {
  analyst: "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/25",
  executor: "bg-ork-green/15 text-ork-green border-ork-green/25",
  reviewer: "bg-ork-purple/15 text-ork-purple border-ork-purple/25",
  planner: "bg-ork-amber/15 text-ork-amber border-ork-amber/25",
  monitor: "bg-ork-red/15 text-ork-red border-ork-red/25",
};

const FAMILY_DEFAULT = "bg-ork-dim/20 text-ork-muted border-ork-dim/30";

const STATUS_OPTIONS = ["all", "active", "registered", "tested", "deprecated", "disabled", "archived"];

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [familyFilter, setFamilyFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .listAgents()
      .then(setAgents)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const families = ["all", ...Array.from(new Set(agents.map((a) => a.family)))];

  const filtered = agents.filter((a) => {
    if (familyFilter !== "all" && a.family !== familyFilter) return false;
    if (statusFilter !== "all" && a.status !== statusFilter) return false;
    return true;
  });

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-wide">AGENT REGISTRY</h1>
          <p className="text-xs text-ork-dim font-mono mt-0.5">
            Registered AI agents and their capabilities
          </p>
        </div>
        <div className="text-xs font-mono text-ork-dim">
          {filtered.length} agent{filtered.length !== 1 ? "s" : ""}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div>
          <span className="data-label mr-2">Family</span>
          <div className="inline-flex gap-1">
            {families.map((f) => (
              <button
                key={f}
                onClick={() => setFamilyFilter(f)}
                className={`px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider rounded border transition-colors duration-150 ${
                  familyFilter === f
                    ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                    : "bg-ork-surface text-ork-muted border-ork-border hover:border-ork-cyan/20 hover:text-ork-text"
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>
        <div>
          <span className="data-label mr-2">Status</span>
          <div className="inline-flex gap-1">
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
            Loading agents...
          </div>
        </div>
      ) : error ? (
        <div className="glass-panel p-8 text-center">
          <p className="text-ork-red font-mono text-sm">Error: {error}</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <p className="text-ork-muted font-mono text-sm">No agents found</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((agent) => (
            <div
              key={agent.id}
              className="glass-panel-hover p-4 flex flex-col gap-3"
            >
              {/* Name + ID */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <h3 className="text-sm font-semibold text-ork-text">
                    {agent.name}
                  </h3>
                  <StatusBadge status={agent.status} />
                </div>
                <p className="font-mono text-[10px] text-ork-dim">
                  {agent.id}
                </p>
              </div>

              {/* Family Tag */}
              <div>
                <span
                  className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${
                    FAMILY_COLORS[agent.family] || FAMILY_DEFAULT
                  }`}
                >
                  {agent.family}
                </span>
              </div>

              {/* Purpose */}
              <p className="text-xs text-ork-muted leading-relaxed line-clamp-2">
                {agent.purpose}
              </p>

              {/* Skills */}
              {agent.skills && agent.skills.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {agent.skills.map((skill) => (
                    <span
                      key={skill}
                      className="text-[9px] font-mono text-ork-dim bg-ork-panel px-1.5 py-0.5 rounded border border-ork-border"
                    >
                      {skill}
                    </span>
                  ))}
                </div>
              )}

              {/* Meta row */}
              <div className="flex items-center gap-3 text-[10px] font-mono text-ork-dim border-t border-ork-border pt-3 mt-auto">
                <span>
                  v<span className="text-ork-muted">{agent.version}</span>
                </span>
                <span className="text-ork-border">|</span>
                <span>
                  crit:{" "}
                  <span
                    className={
                      agent.criticality === "critical"
                        ? "text-ork-red"
                        : agent.criticality === "high"
                        ? "text-ork-amber"
                        : "text-ork-muted"
                    }
                  >
                    {agent.criticality}
                  </span>
                </span>
                <span className="text-ork-border">|</span>
                <span>
                  cost: <span className="text-ork-muted">{agent.cost_profile}</span>
                </span>
              </div>

              {/* Allowed MCPs */}
              <div className="text-[10px] font-mono text-ork-dim">
                <span className="text-ork-muted">
                  {agent.allowed_mcps?.length ?? 0}
                </span>{" "}
                allowed MCPs
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
