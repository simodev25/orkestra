"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { StatCard } from "@/components/ui/stat-card";
import {
  getMcp,
  getMcpHealth,
  getMcpUsage,
  testMcp,
  listMcps,
  getCompatibilityHints,
} from "@/lib/mcp/service";
import type {
  McpDefinition,
  McpHealth,
  McpUsageSummary,
  McpTestResult,
  McpCompatibilityHint,
} from "@/lib/mcp/types";
import { EFFECT_TYPE_META, STATUS_META } from "@/lib/mcp/types";

// ────────────────────────────────────────────────────────────
// Constants
// ────────────────────────────────────────────────────────────
type TabKey = "playground" | "health" | "usage" | "compatibility";

const TABS: { key: TabKey; label: string }[] = [
  { key: "playground", label: "Playground" },
  { key: "health", label: "Health" },
  { key: "usage", label: "Usage" },
  { key: "compatibility", label: "Compatibility" },
];

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

function latencyColor(ms: number): string {
  if (ms < 100) return "text-ork-green";
  if (ms < 500) return "text-ork-amber";
  return "text-ork-red";
}

function colorToAccent(color: string | undefined): "green" | "amber" | "red" | "cyan" | "purple" | undefined {
  const map: Record<string, "green" | "amber" | "red" | "cyan" | "purple"> = {
    "text-ork-green": "green",
    "text-ork-amber": "amber",
    "text-ork-red": "red",
    "text-ork-cyan": "cyan",
    "text-ork-purple": "purple",
  };
  return color ? map[color] : undefined;
}

function fmtTimestamp(ts: string | null): string {
  if (!ts) return "---";
  try {
    return new Date(ts).toLocaleString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return ts;
  }
}

// ────────────────────────────────────────────────────────────
// Page
// ────────────────────────────────────────────────────────────
export default function McpToolkitDetailPage() {
  const params = useParams<{ id: string }>();
  const mcpId = params.id;

  const [activeTab, setActiveTab] = useState<TabKey>("playground");
  const [mcp, setMcp] = useState<McpDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Playground state
  const [toolAction, setToolAction] = useState("");
  const [toolKwargs, setToolKwargs] = useState("{}");
  const [running, setRunning] = useState(false);
  const [testHistory, setTestHistory] = useState<McpTestResult[]>([]);

  // Health state
  const [health, setHealth] = useState<McpHealth | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);

  // Usage state
  const [usage, setUsage] = useState<McpUsageSummary | null>(null);
  const [usageLoading, setUsageLoading] = useState(false);

  // Compatibility state
  const [compat, setCompat] = useState<McpCompatibilityHint | null>(null);
  const [compatLoading, setCompatLoading] = useState(false);
  const [allMcps, setAllMcps] = useState<McpDefinition[]>([]);

  // ── Load MCP definition ──────────────────────────────────
  useEffect(() => {
    if (!mcpId) return;
    setLoading(true);
    setError(null);
    getMcp(mcpId)
      .then(setMcp)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load MCP"))
      .finally(() => setLoading(false));
  }, [mcpId]);

  // ── Load tab-specific data on tab switch ─────────────────
  useEffect(() => {
    if (!mcpId) return;

    if (activeTab === "health" && !health) {
      setHealthLoading(true);
      getMcpHealth(mcpId)
        .then(setHealth)
        .finally(() => setHealthLoading(false));
    }

    if (activeTab === "usage" && !usage) {
      setUsageLoading(true);
      getMcpUsage(mcpId)
        .then(setUsage)
        .finally(() => setUsageLoading(false));
    }

    if (activeTab === "compatibility" && !compat && mcp) {
      setCompatLoading(true);
      listMcps()
        .then((all) => {
          setAllMcps(all);
          const hints = getCompatibilityHints(mcp, all);
          setCompat(hints);
        })
        .finally(() => setCompatLoading(false));
    }
  }, [activeTab, mcpId, mcp, health, usage, compat]);

  // ── Run test ──────────────────────────────────────────────
  const handleRunTest = useCallback(async () => {
    if (!mcpId) return;
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(toolKwargs);
    } catch {
      setTestHistory((prev) => [
        {
          mcp_id: mcpId,
          success: false,
          latency_ms: 0,
          output: null,
          error: "Invalid JSON in tool_kwargs",
        },
        ...prev,
      ]);
      return;
    }

    setRunning(true);
    try {
      const result = await testMcp(mcpId, {
        tool_action: toolAction.trim() || null,
        tool_kwargs: parsed,
      });
      setTestHistory((prev) => [result, ...prev]);
    } finally {
      setRunning(false);
    }
  }, [mcpId, toolAction, toolKwargs]);

  // ── Effect type metadata ──────────────────────────────────
  const effectMeta = mcp
    ? EFFECT_TYPE_META[mcp.effect_type as keyof typeof EFFECT_TYPE_META]
    : null;

  // ── Loading / Error states ────────────────────────────────
  if (loading) {
    return (
      <div className="p-6 max-w-[1400px] mx-auto">
        <div className="glass-panel p-12 text-center">
          <div className="text-ork-cyan font-mono text-sm animate-pulse">
            Loading MCP Toolkit...
          </div>
        </div>
      </div>
    );
  }

  if (error || !mcp) {
    return (
      <div className="p-6 max-w-[1400px] mx-auto space-y-4">
        <Link
          href="/mcps/toolkit"
          className="inline-flex items-center gap-1.5 text-xs font-mono text-ork-dim hover:text-ork-cyan transition-colors"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5" />
            <path d="M12 19l-7-7 7-7" />
          </svg>
          BACK TO TOOLKIT
        </Link>
        <div className="glass-panel p-8 text-center">
          <p className="text-ork-red font-mono text-sm">
            {error || "MCP not found"}
          </p>
        </div>
      </div>
    );
  }

  // ────────────────────────────────────────────────────────────
  // Render
  // ────────────────────────────────────────────────────────────
  return (
    <div className="p-6 max-w-[1400px] mx-auto space-y-6">
      {/* Back link */}
      <Link
        href="/mcps/toolkit"
        className="inline-flex items-center gap-1.5 text-xs font-mono text-ork-dim hover:text-ork-cyan transition-colors"
      >
        <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M19 12H5" />
          <path d="M12 19l-7-7 7-7" />
        </svg>
        BACK TO TOOLKIT
      </Link>

      {/* MCP header */}
      <div className="glass-panel p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold tracking-wide">{mcp.name}</h1>
            <span
              className={`inline-flex items-center px-2.5 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${
                EFFECT_PILL[mcp.effect_type] || EFFECT_PILL_DEFAULT
              }`}
            >
              {effectMeta?.label ?? mcp.effect_type}
            </span>
            <StatusBadge status={mcp.status} />
          </div>
          <span className="text-[10px] font-mono text-ork-dim">
            {mcp.id} &middot; v{mcp.version}
          </span>
        </div>
        <p className="text-xs text-ork-muted mt-2 leading-relaxed max-w-3xl">
          {mcp.purpose}
        </p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2 text-xs font-mono uppercase tracking-wider rounded-t border border-b-0 transition-colors duration-150 ${
              activeTab === tab.key
                ? "bg-ork-surface text-ork-cyan border-ork-cyan/40"
                : "bg-transparent text-ork-muted border-ork-border hover:text-ork-text hover:border-ork-dim"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="glass-panel p-6 -mt-[1px] border-t border-ork-border animate-fade-in">
        {activeTab === "playground" && (
          <PlaygroundTab
            mcp={mcp}
            toolAction={toolAction}
            setToolAction={setToolAction}
            toolKwargs={toolKwargs}
            setToolKwargs={setToolKwargs}
            running={running}
            onRun={handleRunTest}
            testHistory={testHistory}
          />
        )}
        {activeTab === "health" && (
          <HealthTab health={health} loading={healthLoading} />
        )}
        {activeTab === "usage" && (
          <UsageTab usage={usage} loading={usageLoading} />
        )}
        {activeTab === "compatibility" && (
          <CompatibilityTab
            compat={compat}
            loading={compatLoading}
            allMcps={allMcps}
          />
        )}
      </div>
    </div>
  );
}

// ================================================================
// TAB 1: PLAYGROUND
// ================================================================
function PlaygroundTab({
  mcp,
  toolAction,
  setToolAction,
  toolKwargs,
  setToolKwargs,
  running,
  onRun,
  testHistory,
}: {
  mcp: McpDefinition;
  toolAction: string;
  setToolAction: (v: string) => void;
  toolKwargs: string;
  setToolKwargs: (v: string) => void;
  running: boolean;
  onRun: () => void;
  testHistory: McpTestResult[];
}) {
  return (
    <div className="space-y-6">
      {/* Input section */}
      <div className="space-y-4">
        <h2 className="section-title">Input</h2>

        <div>
          <label className="data-label block mb-1.5">tool_action (optional)</label>
          <input
            type="text"
            value={toolAction}
            onChange={(e) => setToolAction(e.target.value)}
            placeholder="e.g. search, lookup, parse..."
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim outline-none focus:border-ork-cyan/40 transition-colors"
          />
        </div>

        <div>
          <label className="data-label block mb-1.5">tool_kwargs (JSON)</label>
          <textarea
            value={toolKwargs}
            onChange={(e) => setToolKwargs(e.target.value)}
            rows={8}
            spellCheck={false}
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim outline-none focus:border-ork-cyan/40 transition-colors resize-y"
            placeholder='{ "query": "example" }'
          />
        </div>

        <button
          onClick={onRun}
          disabled={running}
          className={`px-6 py-2.5 text-xs font-mono uppercase tracking-wider rounded border transition-all duration-200 ${
            running
              ? "bg-ork-dim/20 text-ork-muted border-ork-dim cursor-wait"
              : "bg-ork-cyan/10 text-ork-cyan border-ork-cyan/40 hover:bg-ork-cyan/20 hover:border-ork-cyan/60"
          }`}
        >
          {running ? "RUNNING..." : "RUN TEST"}
        </button>
      </div>

      {/* Result section */}
      {testHistory.length > 0 && (
        <div className="space-y-4">
          <h2 className="section-title">Results</h2>

          {testHistory.map((result, i) => (
            <div
              key={i}
              className={`glass-panel p-4 space-y-3 border-l-2 ${
                result.success ? "border-l-ork-green" : "border-l-ork-red"
              }`}
            >
              {/* Header row */}
              <div className="flex items-center gap-4 flex-wrap">
                {/* Success / failure indicator */}
                <div className="flex items-center gap-2">
                  {result.success ? (
                    <svg className="w-4 h-4 text-ork-green" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M20 6L9 17l-5-5" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4 text-ork-red" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 6L6 18" />
                      <path d="M6 6l12 12" />
                    </svg>
                  )}
                  <span
                    className={`text-xs font-mono font-semibold ${
                      result.success ? "text-ork-green" : "text-ork-red"
                    }`}
                  >
                    {result.success ? "SUCCESS" : "FAILURE"}
                  </span>
                </div>

                {/* Latency */}
                <span className={`text-xs font-mono ${latencyColor(result.latency_ms)}`}>
                  {result.latency_ms}ms
                </span>

                {/* Run index */}
                <span className="text-[10px] font-mono text-ork-dim ml-auto">
                  run #{testHistory.length - i}
                </span>
              </div>

              {/* Output */}
              {result.output && (
                <div>
                  <span className="data-label block mb-1">Output</span>
                  <pre className="bg-ork-bg border border-ork-border rounded p-3 text-xs font-mono text-ork-text overflow-x-auto whitespace-pre-wrap max-h-64 overflow-y-auto">
                    <code>{tryPrettyJson(result.output)}</code>
                  </pre>
                </div>
              )}

              {/* Error */}
              {result.error && (
                <div>
                  <span className="data-label block mb-1">Error</span>
                  <pre className="bg-ork-red/5 border border-ork-red/20 rounded p-3 text-xs font-mono text-ork-red overflow-x-auto whitespace-pre-wrap">
                    <code>{result.error}</code>
                  </pre>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ================================================================
// TAB 2: HEALTH
// ================================================================
function HealthTab({
  health,
  loading,
}: {
  health: McpHealth | null;
  loading: boolean;
}) {
  if (loading || !health) {
    return (
      <div className="text-center py-12">
        <span className="text-ork-cyan font-mono text-sm animate-pulse">
          Loading health data...
        </span>
      </div>
    );
  }

  const failurePercent = health.failure_rate != null ? (health.failure_rate * 100) : 0;
  const failureBarColor =
    failurePercent < 5 ? "bg-ork-green" : failurePercent < 20 ? "bg-ork-amber" : "bg-ork-red";

  return (
    <div className="space-y-6">
      {/* Primary indicator */}
      <div className="flex items-center gap-4">
        <div
          className={`w-5 h-5 rounded-full ${
            health.healthy ? "bg-ork-green" : "bg-ork-red"
          }`}
          style={{
            boxShadow: health.healthy
              ? "0 0 16px rgba(16,185,129,0.5)"
              : "0 0 16px rgba(239,68,68,0.5)",
          }}
        />
        <div>
          <span className="text-sm font-semibold">
            {health.healthy ? "HEALTHY" : "UNHEALTHY"}
          </span>
          <span className="text-xs font-mono text-ork-dim ml-3">
            Status: {health.status}
          </span>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Invocations" value={health.total_invocations.toLocaleString()} />
        <StatCard
          label="Failure Rate"
          value={`${failurePercent.toFixed(1)}%`}
          accent={colorToAccent(failurePercent < 5 ? "text-ork-green" : failurePercent < 20 ? "text-ork-amber" : "text-ork-red")}
        />
        <StatCard
          label="Avg Latency"
          value={health.avg_latency_ms != null ? `${health.avg_latency_ms.toFixed(0)}ms` : "---"}
          accent={colorToAccent(health.avg_latency_ms != null ? latencyColor(health.avg_latency_ms) : undefined)}
        />
        <StatCard
          label="Last Check"
          value={fmtTimestamp(health.last_check_at)}
        />
      </div>

      {/* Failure rate bar */}
      <div className="glass-panel p-4 space-y-2">
        <span className="data-label">Failure Rate Visual</span>
        <div className="w-full h-3 bg-ork-bg rounded-full overflow-hidden border border-ork-border">
          <div
            className={`h-full rounded-full transition-all duration-500 ${failureBarColor}`}
            style={{ width: `${Math.min(failurePercent, 100)}%` }}
          />
        </div>
        <div className="flex justify-between text-[10px] font-mono text-ork-dim">
          <span>0%</span>
          <span>{failurePercent.toFixed(1)}%</span>
          <span>100%</span>
        </div>
      </div>

      {/* Timestamps */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="glass-panel p-4">
          <span className="data-label block mb-1">Last Success</span>
          <span className="text-sm font-mono text-ork-green">
            {fmtTimestamp(health.last_success_at)}
          </span>
        </div>
        <div className="glass-panel p-4">
          <span className="data-label block mb-1">Last Failure</span>
          <span className="text-sm font-mono text-ork-red">
            {fmtTimestamp(health.last_failure_at)}
          </span>
        </div>
      </div>

      {/* Recent errors */}
      {health.recent_errors.length > 0 && (
        <div className="space-y-3">
          <h3 className="section-title">Recent Errors</h3>
          {health.recent_errors.map((err, i) => (
            <div
              key={i}
              className="glass-panel border-l-2 border-l-ork-red p-4"
            >
              <pre className="text-xs font-mono text-ork-red/90 whitespace-pre-wrap break-words">
                {err}
              </pre>
            </div>
          ))}
        </div>
      )}

      {health.recent_errors.length === 0 && (
        <div className="glass-panel p-6 text-center">
          <span className="text-xs font-mono text-ork-dim">No recent errors recorded</span>
        </div>
      )}
    </div>
  );
}

// ================================================================
// TAB 3: USAGE
// ================================================================
function UsageTab({
  usage,
  loading,
}: {
  usage: McpUsageSummary | null;
  loading: boolean;
}) {
  if (loading || !usage) {
    return (
      <div className="text-center py-12">
        <span className="text-ork-cyan font-mono text-sm animate-pulse">
          Loading usage data...
        </span>
      </div>
    );
  }

  const statusEntries = Object.entries(usage.invocations_by_status);
  const maxCount = Math.max(...statusEntries.map(([, v]) => v), 1);

  const STATUS_BAR_COLORS: Record<string, string> = {
    success: "bg-ork-green",
    completed: "bg-ork-green",
    failed: "bg-ork-red",
    error: "bg-ork-red",
    timeout: "bg-ork-amber",
    pending: "bg-ork-purple",
    running: "bg-ork-cyan",
  };

  return (
    <div className="space-y-6">
      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Total Invocations" value={usage.total_invocations.toLocaleString()} />
        <StatCard label="Total Cost" value={`$${usage.total_cost.toFixed(2)}`} />
        <StatCard
          label="Avg Latency"
          value={`${usage.avg_latency_ms.toFixed(0)}ms`}
          accent={colorToAccent(latencyColor(usage.avg_latency_ms))}
        />
        <StatCard label="Avg Cost / Invocation" value={`$${usage.avg_cost.toFixed(4)}`} />
      </div>

      {/* Agents using this MCP */}
      <div className="glass-panel p-4 space-y-3">
        <h3 className="section-title">Agents Using This MCP</h3>
        {usage.agents_using.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {usage.agents_using.map((agentId) => (
              <Link
                key={agentId}
                href="/agents"
                className="inline-flex items-center px-2.5 py-1 text-[11px] font-mono bg-ork-cyan/10 text-ork-cyan border border-ork-cyan/20 rounded hover:bg-ork-cyan/20 hover:border-ork-cyan/40 transition-colors"
              >
                {agentId}
              </Link>
            ))}
          </div>
        ) : (
          <span className="text-xs font-mono text-ork-dim">No agents currently using this MCP</span>
        )}
      </div>

      {/* Invocations by status — horizontal bar chart */}
      {statusEntries.length > 0 && (
        <div className="glass-panel p-4 space-y-3">
          <h3 className="section-title">Invocations by Status</h3>
          <div className="space-y-2">
            {statusEntries.map(([status, count]) => {
              const pct = (count / maxCount) * 100;
              const barColor = STATUS_BAR_COLORS[status] || "bg-ork-dim";
              return (
                <div key={status} className="flex items-center gap-3">
                  <span className="text-[11px] font-mono text-ork-muted w-20 text-right shrink-0 uppercase">
                    {status}
                  </span>
                  <div className="flex-1 h-5 bg-ork-bg rounded border border-ork-border overflow-hidden">
                    <div
                      className={`h-full rounded transition-all duration-500 ${barColor}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-[11px] font-mono text-ork-text w-16 shrink-0">
                    {count.toLocaleString()}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Impact if disabled */}
      <div className="glass-panel p-4 space-y-3 border-l-2 border-l-ork-amber">
        <h3 className="section-title flex items-center gap-2">
          <svg className="w-3.5 h-3.5 text-ork-amber" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          Impact if Disabled
        </h3>
        {usage.agents_using.length > 0 ? (
          <>
            <p className="text-xs text-ork-muted">
              Disabling this MCP would affect{" "}
              <span className="text-ork-amber font-semibold">{usage.agents_using.length}</span>{" "}
              agent{usage.agents_using.length !== 1 ? "s" : ""}:
            </p>
            <div className="flex flex-wrap gap-2">
              {usage.agents_using.map((agentId) => (
                <span
                  key={agentId}
                  className="inline-flex items-center px-2.5 py-1 text-[11px] font-mono bg-ork-amber/10 text-ork-amber border border-ork-amber/20 rounded"
                >
                  {agentId}
                </span>
              ))}
            </div>
          </>
        ) : (
          <p className="text-xs text-ork-dim font-mono">
            No agents are currently using this MCP. It can be safely disabled.
          </p>
        )}
      </div>
    </div>
  );
}

// ================================================================
// TAB 4: COMPATIBILITY
// ================================================================
function CompatibilityTab({
  compat,
  loading,
  allMcps,
}: {
  compat: McpCompatibilityHint | null;
  loading: boolean;
  allMcps: McpDefinition[];
}) {
  if (loading || !compat) {
    return (
      <div className="text-center py-12">
        <span className="text-ork-cyan font-mono text-sm animate-pulse">
          Computing compatibility hints...
        </span>
      </div>
    );
  }

  const similarMcpDefs = allMcps.filter((m) => compat.similar_mcps.includes(m.id));

  return (
    <div className="space-y-6">
      {/* Compatible agent families */}
      <div className="glass-panel p-4 space-y-3">
        <h3 className="section-title">Compatible Agent Families</h3>
        {compat.compatible_agent_families.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {compat.compatible_agent_families.map((family) => (
              <span
                key={family}
                className="inline-flex items-center px-2.5 py-1 text-[11px] font-mono bg-ork-purple/10 text-ork-purple border border-ork-purple/20 rounded capitalize"
              >
                {family}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-xs font-mono text-ork-dim">No compatible families identified</span>
        )}
      </div>

      {/* Compatible use cases */}
      <div className="glass-panel p-4 space-y-3">
        <h3 className="section-title">Compatible Use Cases</h3>
        {compat.compatible_use_cases.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {compat.compatible_use_cases.map((uc) => (
              <span
                key={uc}
                className="inline-flex items-center px-2.5 py-1 text-[11px] font-mono bg-ork-green/10 text-ork-green border border-ork-green/20 rounded"
              >
                {uc.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-xs font-mono text-ork-dim">No compatible use cases identified</span>
        )}
      </div>

      {/* Similar MCPs */}
      <div className="space-y-3">
        <h3 className="section-title">Similar MCPs in Catalog</h3>
        {similarMcpDefs.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {similarMcpDefs.map((sim) => (
              <Link
                key={sim.id}
                href={`/mcps/${sim.id}/toolkit`}
                className="glass-panel-hover p-4 flex flex-col gap-2 group"
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-semibold text-ork-text group-hover:text-ork-cyan transition-colors">
                    {sim.name}
                  </h4>
                  <StatusBadge status={sim.status} />
                </div>
                <p className="font-mono text-[10px] text-ork-dim">{sim.id}</p>
                <p className="text-xs text-ork-muted line-clamp-2">
                  {sim.purpose}
                </p>
                <div className="flex items-center gap-2 mt-auto pt-2 border-t border-ork-border">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${
                      EFFECT_PILL[sim.effect_type] || EFFECT_PILL_DEFAULT
                    }`}
                  >
                    {sim.effect_type}
                  </span>
                  <span className="text-[10px] font-mono text-ork-cyan opacity-0 group-hover:opacity-100 transition-opacity ml-auto">
                    OPEN &rarr;
                  </span>
                </div>
              </Link>
            ))}
          </div>
        ) : (
          <div className="glass-panel p-6 text-center">
            <span className="text-xs font-mono text-ork-dim">
              No similar MCPs found with the same effect type
            </span>
          </div>
        )}
      </div>

      {/* Suggested effect chain */}
      <div className="glass-panel p-4 space-y-3">
        <h3 className="section-title">Suggested Effect Chain</h3>
        <div className="flex items-center gap-2 flex-wrap">
          {compat.suggested_effect_chain.map((effect, i) => {
            const meta = EFFECT_TYPE_META[effect as keyof typeof EFFECT_TYPE_META];
            return (
              <div key={`${effect}-${i}`} className="flex items-center gap-2">
                {i > 0 && (
                  <svg className="w-4 h-4 text-ork-dim shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14" />
                    <path d="M12 5l7 7-7 7" />
                  </svg>
                )}
                <span
                  className={`inline-flex items-center px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider border rounded ${
                    EFFECT_PILL[effect] || EFFECT_PILL_DEFAULT
                  }`}
                >
                  {meta?.label ?? effect}
                </span>
              </div>
            );
          })}
        </div>
        <p className="text-[10px] font-mono text-ork-dim mt-1">
          Recommended pipeline ordering for this effect type
        </p>
      </div>
    </div>
  );
}

// ================================================================
// Helpers
// ================================================================
function tryPrettyJson(raw: string): string {
  try {
    const parsed = JSON.parse(raw);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return raw;
  }
}
