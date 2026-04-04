"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { listMcps, getCatalogStats } from "@/lib/mcp/service";
import type { McpDefinition, McpCatalogStats, McpCatalogFilterState } from "@/lib/mcp/types";
import { EFFECT_TYPE_META, CRITICALITY_META } from "@/lib/mcp/types";

/* ── colour helpers ─────────────────────────────────────────── */

const effectColor = (c: string) =>
  ({
    cyan: "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30",
    purple: "bg-ork-purple/15 text-ork-purple border-ork-purple/30",
    green: "bg-ork-green/15 text-ork-green border-ork-green/30",
    amber: "bg-ork-amber/15 text-ork-amber border-ork-amber/30",
    red: "bg-ork-red/15 text-ork-red border-ork-red/30",
  })[c] ?? "bg-ork-dim/20 text-ork-muted border-ork-dim/30";

const critColor = (c: string) =>
  ({
    green: "text-ork-green",
    amber: "text-ork-amber",
    red: "text-ork-red",
  })[c] ?? "text-ork-muted";

/* ── static filter options ──────────────────────────────────── */

const EFFECT_OPTIONS = ["all", "read", "search", "compute", "generate", "validate", "write", "act"] as const;
const STATUS_OPTIONS = ["all", "active", "degraded", "disabled", "draft"] as const;
const CRIT_OPTIONS = ["all", "low", "medium", "high"] as const;

/* ── icons (inline SVG) ─────────────────────────────────────── */

function LockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function AuditIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function ToolkitIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

/* ── filter pill button ─────────────────────────────────────── */

function FilterPill({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider rounded border transition-colors duration-150 ${
        active
          ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
          : "bg-ork-surface text-ork-muted border-ork-border hover:border-ork-cyan/20 hover:text-ork-text"
      }`}
    >
      {label}
    </button>
  );
}

/* ════════════════════════════════════════════════════════════════
   MCP CATALOG PAGE
   ════════════════════════════════════════════════════════════════ */

export default function McpCatalogPage() {
  const [mcps, setMcps] = useState<McpDefinition[]>([]);
  const [stats, setStats] = useState<McpCatalogStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<McpCatalogFilterState>({
    search: "",
    status: "all",
    criticality: "all",
    effect_type: "all",
    approval_required: "all",
    audit_required: "all",
    cost_profile: "all",
  });

  useEffect(() => {
    Promise.all([listMcps(), getCatalogStats()])
      .then(([data, s]) => {
        setMcps(data);
        setStats(s);
      })
      .finally(() => setLoading(false));
  }, []);

  /* ── client-side filtering ──────────────────────────────────── */

  const filtered = useMemo(() => {
    return mcps.filter((m) => {
      if (filters.search) {
        const q = filters.search.toLowerCase();
        if (
          !m.name.toLowerCase().includes(q) &&
          !m.id.toLowerCase().includes(q) &&
          !m.purpose.toLowerCase().includes(q)
        )
          return false;
      }
      if (filters.effect_type !== "all" && m.effect_type !== filters.effect_type) return false;
      if (filters.status !== "all" && m.status !== filters.status) return false;
      if (filters.criticality !== "all" && m.criticality !== filters.criticality) return false;
      return true;
    });
  }, [mcps, filters]);

  const setFilter = <K extends keyof McpCatalogFilterState>(key: K, val: McpCatalogFilterState[K]) =>
    setFilters((prev) => ({ ...prev, [key]: val }));

  /* ── stat pill helper ───────────────────────────────────────── */

  function StatPill({ label, value, color }: { label: string; value: number; color: string }) {
    const textClass =
      ({ cyan: "text-ork-cyan", green: "text-ork-green", amber: "text-ork-amber", red: "text-ork-red", purple: "text-ork-purple" })[color] ?? "text-ork-text";
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 bg-ork-surface border border-ork-border rounded">
        <span className={`font-mono text-sm font-semibold ${textClass}`}>{value}</span>
        <span className="text-[10px] font-mono uppercase tracking-wider text-ork-dim">{label}</span>
      </div>
    );
  }

  /* ── render ──────────────────────────────────────────────────── */

  return (
    <div className="p-6 max-w-[1440px] mx-auto space-y-6 animate-fade-in">
      {/* ━━ Header ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-wide text-ork-text">MCP CATALOG</h1>
          <p className="text-xs text-ork-dim font-mono mt-1 tracking-wide">Governed capability registry</p>
        </div>
        {/* Action buttons */}
        <div className="flex items-center gap-3">
          <Link
            href="/mcps/new"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-cyan/10 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/20 transition-colors"
          >
            <PlusIcon className="w-3.5 h-3.5" />
            Add MCP
          </Link>
          <Link
            href="/mcps/toolkit"
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-surface text-ork-muted border border-ork-border rounded hover:border-ork-purple/30 hover:text-ork-purple transition-colors"
          >
            <ToolkitIcon className="w-3.5 h-3.5" />
            Open Toolkit
          </Link>
        </div>
      </div>

      {/* ━━ Stats bar ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      {stats && (
        <div className="flex items-center gap-2 flex-wrap">
          <StatPill label="Total" value={stats.total} color="cyan" />
          <StatPill label="Active" value={stats.active} color="green" />
          <StatPill label="Degraded" value={stats.degraded} color="amber" />
          <StatPill label="Disabled" value={stats.disabled} color="red" />
          <StatPill label="Critical" value={stats.critical} color="red" />
          <StatPill label="Approval" value={stats.approval_required} color="purple" />
        </div>
      )}

      {/* ━━ Filters bar ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <div className="glass-panel p-4 space-y-3">
        {/* Search */}
        <div className="flex items-center gap-3">
          <label className="data-label shrink-0">Search</label>
          <input
            type="text"
            value={filters.search}
            onChange={(e) => setFilter("search", e.target.value)}
            placeholder="Filter by name, ID, or purpose..."
            className="flex-1 bg-ork-bg border border-ork-border rounded px-3 py-1.5 text-sm font-mono text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40 transition-colors"
          />
          <span className="text-xs font-mono text-ork-dim shrink-0">
            {filtered.length}/{mcps.length}
          </span>
        </div>

        {/* Filter rows */}
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
          {/* Effect type */}
          <div className="flex items-center gap-2">
            <span className="data-label shrink-0">Effect</span>
            <div className="flex gap-1 flex-wrap">
              {EFFECT_OPTIONS.map((e) => (
                <FilterPill key={e} label={e} active={filters.effect_type === e} onClick={() => setFilter("effect_type", e)} />
              ))}
            </div>
          </div>

          {/* Status */}
          <div className="flex items-center gap-2">
            <span className="data-label shrink-0">Status</span>
            <div className="flex gap-1 flex-wrap">
              {STATUS_OPTIONS.map((s) => (
                <FilterPill key={s} label={s} active={filters.status === s} onClick={() => setFilter("status", s)} />
              ))}
            </div>
          </div>

          {/* Criticality */}
          <div className="flex items-center gap-2">
            <span className="data-label shrink-0">Crit</span>
            <div className="flex gap-1 flex-wrap">
              {CRIT_OPTIONS.map((c) => (
                <FilterPill key={c} label={c} active={filters.criticality === c} onClick={() => setFilter("criticality", c)} />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ━━ Content ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      {loading ? (
        <div className="glass-panel p-16 text-center">
          <div className="inline-block w-6 h-6 border-2 border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin mb-3" />
          <p className="text-sm font-mono text-ork-cyan animate-pulse">Loading MCP catalog...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel p-16 text-center space-y-2">
          <p className="text-sm font-mono text-ork-muted">No capabilities match the current filters</p>
          <button
            onClick={() =>
              setFilters({ search: "", status: "all", criticality: "all", effect_type: "all", approval_required: "all", audit_required: "all", cost_profile: "all" })
            }
            className="text-xs font-mono text-ork-cyan hover:underline"
          >
            Reset all filters
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {filtered.map((mcp) => {
            const eMeta = EFFECT_TYPE_META[mcp.effect_type];
            const cMeta = CRITICALITY_META[mcp.criticality];
            return (
              <div key={mcp.id} className="glass-panel-hover p-5 flex flex-col gap-3 group">
                {/* ─ Row 1: Name + Status ─ */}
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-ork-text truncate">{mcp.name}</h3>
                    <p className="font-mono text-[10px] text-ork-dim mt-0.5 truncate">{mcp.id}</p>
                  </div>
                  <StatusBadge status={mcp.status} />
                </div>

                {/* ─ Row 2: Purpose ─ */}
                <p className="text-xs text-ork-muted leading-relaxed line-clamp-2">{mcp.purpose}</p>

                {/* ─ Row 3: Badges ─ */}
                <div className="flex items-center gap-2 flex-wrap">
                  {/* Effect type */}
                  <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${effectColor(eMeta.color)}`}>
                    {eMeta.label}
                  </span>
                  {/* Criticality */}
                  <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${effectColor(cMeta.color)}`}>
                    {cMeta.label} risk
                  </span>
                  {/* Approval */}
                  {mcp.approval_required && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-ork-amber bg-ork-amber/10 border border-ork-amber/20 rounded">
                      <LockIcon className="w-2.5 h-2.5" />
                      Approval
                    </span>
                  )}
                  {/* Audit */}
                  {mcp.audit_required && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider text-ork-purple bg-ork-purple/10 border border-ork-purple/20 rounded">
                      <AuditIcon className="w-2.5 h-2.5" />
                      Audit
                    </span>
                  )}
                </div>

                {/* ─ Row 4: Metadata ─ */}
                <div className="flex items-center gap-3 text-[10px] font-mono text-ork-dim border-t border-ork-border pt-3">
                  <span>
                    timeout: <span className="text-ork-muted">{mcp.timeout_seconds}s</span>
                  </span>
                  <span className="text-ork-border">|</span>
                  <span>
                    cost: <span className="text-ork-muted">{mcp.cost_profile}</span>
                  </span>
                  <span className="text-ork-border">|</span>
                  <span>
                    v<span className="text-ork-muted">{mcp.version}</span>
                  </span>
                  <span className="text-ork-border">|</span>
                  <span>
                    <span className={`${critColor(cMeta.color)}`}>{mcp.allowed_agents?.length ?? 0}</span> agents
                  </span>
                </div>

                {/* ─ Row 5: Actions ─ */}
                <div className="flex items-center gap-2 pt-1 mt-auto">
                  <Link
                    href={`/mcps/${mcp.id}`}
                    className="px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider bg-ork-cyan/8 text-ork-cyan border border-ork-cyan/20 rounded hover:bg-ork-cyan/15 transition-colors"
                  >
                    Details
                  </Link>
                  <Link
                    href={`/mcps/${mcp.id}/toolkit`}
                    className="px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider bg-ork-surface text-ork-muted border border-ork-border rounded hover:border-ork-purple/30 hover:text-ork-purple transition-colors"
                  >
                    Test
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
