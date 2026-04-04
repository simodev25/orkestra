"use client";

import { useState, useEffect, useMemo } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { listMcps } from "@/lib/mcp/service";
import type { McpDefinition } from "@/lib/mcp/types";
import { EFFECT_TYPE_META, STATUS_META } from "@/lib/mcp/types";

// ────────────────────────────────────────────────────────────
// Effect-type pill color map (Tailwind classes)
// ────────────────────────────────────────────────────────────
const EFFECT_PILL: Record<string, string> = {
  read: "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/25",
  search: "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/25",
  compute: "bg-ork-purple/15 text-ork-purple border-ork-purple/25",
  generate: "bg-ork-purple/15 text-ork-purple border-ork-purple/25",
  validate: "bg-ork-green/15 text-ork-green border-ork-green/25",
  write: "bg-ork-amber/15 text-ork-amber border-ork-amber/25",
  act: "bg-ork-red/15 text-ork-red border-ork-red/25",
};
const EFFECT_PILL_DEFAULT = "bg-ork-dim/20 text-ork-muted border-ork-dim/30";

// ────────────────────────────────────────────────────────────
// Page
// ────────────────────────────────────────────────────────────
export default function McpToolkitIndexPage() {
  const [mcps, setMcps] = useState<McpDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  useEffect(() => {
    setLoading(true);
    setError(null);
    listMcps()
      .then(setMcps)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load MCPs"))
      .finally(() => setLoading(false));
  }, []);

  // Filter by search term
  const filtered = useMemo(() => {
    if (!search.trim()) return mcps;
    const q = search.toLowerCase();
    return mcps.filter(
      (m) =>
        m.name.toLowerCase().includes(q) ||
        m.id.toLowerCase().includes(q) ||
        m.purpose.toLowerCase().includes(q) ||
        m.effect_type.toLowerCase().includes(q),
    );
  }, [mcps, search]);

  // Group by effect_type for visual grouping
  const grouped = useMemo(() => {
    const order = ["read", "search", "compute", "generate", "validate", "write", "act"];
    const map = new Map<string, McpDefinition[]>();
    for (const mcp of filtered) {
      const key = mcp.effect_type;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(mcp);
    }
    // Sort groups by canonical order
    return order
      .filter((k) => map.has(k))
      .map((k) => ({ effect: k, mcps: map.get(k)! }));
  }, [filtered]);

  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      {/* Back link */}
      <Link
        href="/mcps"
        className="inline-flex items-center gap-1.5 text-xs font-mono text-ork-dim hover:text-ork-cyan transition-colors"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5" />
          <path d="M12 19l-7-7 7-7" />
        </svg>
        BACK TO MCP REGISTRY
      </Link>

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <h1 className="text-lg font-semibold tracking-wide">MCP TOOLKIT</h1>
          <p className="text-xs text-ork-dim font-mono mt-0.5">
            Test, inspect, and debug platform capabilities
          </p>
        </div>
        <div className="text-xs font-mono text-ork-dim">
          {filtered.length} MCP{filtered.length !== 1 ? "s" : ""} available
        </div>
      </div>

      {/* Search */}
      <div className="glass-panel p-3 flex items-center gap-3">
        <svg className="w-4 h-4 text-ork-dim shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
        </svg>
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, ID, purpose, or effect type..."
          className="w-full bg-transparent text-sm font-mono text-ork-text placeholder:text-ork-dim outline-none"
        />
        {search && (
          <button
            onClick={() => setSearch("")}
            className="text-ork-dim hover:text-ork-text transition-colors text-xs font-mono"
          >
            CLEAR
          </button>
        )}
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
          <p className="text-ork-muted font-mono text-sm">
            {search ? "No MCPs match your search" : "No MCPs found"}
          </p>
        </div>
      ) : (
        <div className="space-y-8">
          {grouped.map(({ effect, mcps: group }) => {
            const meta = EFFECT_TYPE_META[effect as keyof typeof EFFECT_TYPE_META];
            return (
              <section key={effect}>
                {/* Group header */}
                <div className="flex items-center gap-3 mb-4">
                  <span
                    className={`inline-flex items-center px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider border rounded ${
                      EFFECT_PILL[effect] || EFFECT_PILL_DEFAULT
                    }`}
                  >
                    {meta?.label ?? effect}
                  </span>
                  <div className="h-px flex-1 bg-ork-border" />
                  <span className="text-[10px] font-mono text-ork-dim">
                    {group.length} tool{group.length !== 1 ? "s" : ""}
                  </span>
                </div>

                {/* Cards */}
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {group.map((mcp) => (
                    <Link
                      key={mcp.id}
                      href={`/mcps/${mcp.id}/toolkit`}
                      className="glass-panel-hover p-4 flex flex-col gap-3 cursor-pointer group"
                    >
                      {/* Name + status */}
                      <div className="flex items-center justify-between">
                        <h3 className="text-sm font-semibold text-ork-text group-hover:text-ork-cyan transition-colors">
                          {mcp.name}
                        </h3>
                        <StatusBadge status={mcp.status} />
                      </div>

                      {/* ID */}
                      <p className="font-mono text-[10px] text-ork-dim -mt-1">
                        {mcp.id}
                      </p>

                      {/* Effect pill */}
                      <div className="flex items-center gap-2">
                        <span
                          className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${
                            EFFECT_PILL[mcp.effect_type] || EFFECT_PILL_DEFAULT
                          }`}
                        >
                          {mcp.effect_type}
                        </span>
                      </div>

                      {/* Purpose */}
                      <p className="text-xs text-ork-muted leading-relaxed line-clamp-2">
                        {mcp.purpose}
                      </p>

                      {/* Footer */}
                      <div className="flex items-center justify-between border-t border-ork-border pt-3 mt-auto">
                        <span className="text-[10px] font-mono text-ork-dim">
                          v{mcp.version}
                        </span>
                        <span className="text-[10px] font-mono text-ork-cyan opacity-0 group-hover:opacity-100 transition-opacity">
                          OPEN TOOLKIT &rarr;
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
