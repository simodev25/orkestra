"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { getMcp, getMcpHealth, getMcpUsage } from "@/lib/mcp/service";
import type { McpDefinition, McpHealth, McpUsageSummary } from "@/lib/mcp/types";
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

const accentText = (c: string) =>
  ({
    cyan: "text-ork-cyan",
    green: "text-ork-green",
    amber: "text-ork-amber",
    red: "text-ork-red",
    purple: "text-ork-purple",
  })[c] ?? "text-ork-text";

/* ── icons ──────────────────────────────────────────────────── */

function ArrowLeftIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="19" y1="12" x2="5" y2="12" /><polyline points="12 19 5 12 12 5" />
    </svg>
  );
}

function HeartPulseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M19.5 12.572l-7.5 7.428-7.5-7.428A5 5 0 1 1 12 6.006a5 5 0 1 1 7.5 6.572" />
      <path d="M12 6v4l2 2-2 2v4" />
    </svg>
  );
}

function LockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  );
}

function UnlockIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
      <path d="M7 11V7a5 5 0 0 1 9.9-1" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

/* ── field row component ────────────────────────────────────── */

function Field({ label, children, mono }: { label: string; children: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="data-label">{label}</span>
      <span className={`text-sm text-ork-text ${mono ? "font-mono" : ""}`}>{children}</span>
    </div>
  );
}

/* ── percent bar ────────────────────────────────────────────── */

function PercentBar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  const bg = ({ green: "bg-ork-green", amber: "bg-ork-amber", red: "bg-ork-red", cyan: "bg-ork-cyan" })[color] ?? "bg-ork-cyan";
  return (
    <div className="w-full h-2 bg-ork-bg rounded-full overflow-hidden border border-ork-border">
      <div className={`h-full rounded-full ${bg} transition-all duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}

/* ── format helpers ─────────────────────────────────────────── */

function fmtDate(d: string | null) {
  if (!d) return "--";
  try {
    return new Date(d).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return d;
  }
}

/* ════════════════════════════════════════════════════════════════
   MCP DETAIL PAGE
   ════════════════════════════════════════════════════════════════ */

export default function McpDetailPage() {
  const params = useParams();
  const id = params.id as string;

  const [mcp, setMcp] = useState<McpDefinition | null>(null);
  const [health, setHealth] = useState<McpHealth | null>(null);
  const [usage, setUsage] = useState<McpUsageSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    setError(null);
    Promise.all([getMcp(id), getMcpHealth(id), getMcpUsage(id)])
      .then(([m, h, u]) => {
        setMcp(m);
        setHealth(h);
        setUsage(u);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load MCP"))
      .finally(() => setLoading(false));
  }, [id]);

  /* ── loading / error states ─────────────────────────────────── */

  if (loading) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-16 text-center">
          <div className="inline-block w-6 h-6 border-2 border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin mb-3" />
          <p className="text-sm font-mono text-ork-cyan animate-pulse">Loading MCP definition...</p>
        </div>
      </div>
    );
  }

  if (error || !mcp) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-12 text-center space-y-3">
          <p className="text-sm font-mono text-ork-red">{error ?? "MCP not found"}</p>
          <Link href="/mcps" className="text-xs font-mono text-ork-cyan hover:underline">
            Back to catalog
          </Link>
        </div>
      </div>
    );
  }

  const eMeta = EFFECT_TYPE_META[mcp.effect_type];
  const cMeta = CRITICALITY_META[mcp.criticality];
  const failureRate = health?.failure_rate ?? 0;
  const failureColor = failureRate > 10 ? "red" : failureRate > 2 ? "amber" : "green";

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6 animate-fade-in">
      {/* ━━ Header ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-2">
          <Link href="/mcps" className="inline-flex items-center gap-1 text-xs font-mono text-ork-dim hover:text-ork-cyan transition-colors">
            <ArrowLeftIcon className="w-3 h-3" />
            Back to catalog
          </Link>
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-semibold tracking-wide text-ork-text">{mcp.name}</h1>
            <StatusBadge status={mcp.status} />
          </div>
          <p className="font-mono text-xs text-ork-dim">{mcp.id} <span className="text-ork-border mx-1">|</span> v{mcp.version}</p>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            href={`/mcps/${mcp.id}/edit`}
            className="px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-surface text-ork-muted border border-ork-border rounded hover:border-ork-cyan/30 hover:text-ork-cyan transition-colors"
          >
            Edit
          </Link>
          <Link
            href={`/mcps/${mcp.id}/toolkit`}
            className="px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-purple/10 text-ork-purple border border-ork-purple/30 rounded hover:bg-ork-purple/20 transition-colors"
          >
            Test
          </Link>
          <Link
            href={`/mcps/${mcp.id}/validate`}
            className="px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-cyan/10 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/20 transition-colors"
          >
            Validate
          </Link>
          {mcp.status !== "active" ? (
            <button className="px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-green/10 text-ork-green border border-ork-green/30 rounded hover:bg-ork-green/20 transition-colors">
              Activate
            </button>
          ) : (
            <button className="px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-red/10 text-ork-red border border-ork-red/30 rounded hover:bg-ork-red/20 transition-colors">
              Disable
            </button>
          )}
        </div>
      </div>

      {/* ━━ Quick stats ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Health */}
        <div className={`glass-panel p-4 border-l-2 ${health?.healthy ? "border-ork-green/40" : "border-ork-red/40"}`}>
          <p className="data-label mb-1">Health</p>
          <div className="flex items-center gap-2">
            <HeartPulseIcon className={`w-5 h-5 ${health?.healthy ? "text-ork-green" : "text-ork-red"}`} />
            <span className={`stat-value ${health?.healthy ? "text-ork-green" : "text-ork-red"}`}>
              {health?.healthy ? "Healthy" : "Unhealthy"}
            </span>
          </div>
          <p className="text-xs text-ork-dim font-mono mt-1">
            {failureRate > 0 ? `${failureRate.toFixed(1)}% failure rate` : "No failures"}
          </p>
        </div>

        {/* Invocations */}
        <div className="glass-panel p-4 border-l-2 border-ork-cyan/40">
          <p className="data-label mb-1">Total Invocations</p>
          <p className="stat-value text-ork-cyan">{(health?.total_invocations ?? 0).toLocaleString()}</p>
          <p className="text-xs text-ork-dim font-mono mt-1">lifetime calls</p>
        </div>

        {/* Avg Latency */}
        <div className="glass-panel p-4 border-l-2 border-ork-amber/40">
          <p className="data-label mb-1">Avg Latency</p>
          <p className="stat-value text-ork-amber">
            {health?.avg_latency_ms != null ? `${health.avg_latency_ms}ms` : "--"}
          </p>
          <p className="text-xs text-ork-dim font-mono mt-1">response time</p>
        </div>

        {/* Cost Profile */}
        <div className="glass-panel p-4 border-l-2 border-ork-purple/40">
          <p className="data-label mb-1">Cost Profile</p>
          <p className="stat-value text-ork-purple uppercase">{mcp.cost_profile}</p>
          <p className="text-xs text-ork-dim font-mono mt-1">
            {usage ? `$${usage.total_cost.toFixed(2)} total` : "no usage data"}
          </p>
        </div>
      </div>

      {/* ━━ Section grid ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* ── 1. Identity ──────────────────────────────────────── */}
        <div className="glass-panel p-5 space-y-4">
          <h2 className="section-title">Identity</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="MCP ID" mono>{mcp.id}</Field>
            <Field label="Name">{mcp.name}</Field>
            <Field label="Version" mono>v{mcp.version}</Field>
            <Field label="Status"><StatusBadge status={mcp.status} /></Field>
            <Field label="Owner" mono>{mcp.owner ?? <span className="text-ork-dim italic">Unassigned</span>}</Field>
            <Field label="Created">{fmtDate(mcp.created_at)}</Field>
            <Field label="Updated" mono>{fmtDate(mcp.updated_at)}</Field>
          </div>
        </div>

        {/* ── 2. Purpose & Description ─────────────────────────── */}
        <div className="glass-panel p-5 space-y-4">
          <h2 className="section-title">Purpose & Description</h2>
          <div className="space-y-3">
            <div>
              <span className="data-label">Purpose</span>
              <p className="text-sm text-ork-text mt-1 leading-relaxed font-medium">{mcp.purpose}</p>
            </div>
            <div>
              <span className="data-label">Description</span>
              <p className="text-xs text-ork-muted mt-1 leading-relaxed">
                {mcp.description ?? <span className="italic text-ork-dim">No description provided</span>}
              </p>
            </div>
          </div>
        </div>

        {/* ── 3. Governance (prominent) ────────────────────────── */}
        <div className="glass-panel p-5 space-y-4 border-l-2 border-ork-cyan/30 lg:col-span-2">
          <h2 className="section-title">Governance</h2>
          <div className="flex flex-wrap items-start gap-6">
            {/* Effect Type — large badge */}
            <div className="space-y-1">
              <span className="data-label">Effect Type</span>
              <div className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-mono uppercase tracking-wider border rounded-lg ${effectColor(eMeta.color)}`}>
                <span className="text-base">{eMeta.label}</span>
                <span className="text-[10px] opacity-60">risk: {eMeta.risk}</span>
              </div>
            </div>

            {/* Criticality */}
            <div className="space-y-1">
              <span className="data-label">Criticality</span>
              <div className={`inline-flex items-center px-3 py-2 text-sm font-mono uppercase tracking-wider border rounded-lg ${effectColor(cMeta.color)}`}>
                {cMeta.label}
              </div>
            </div>

            {/* Approval */}
            <div className="space-y-1">
              <span className="data-label">Approval Required</span>
              <div className="flex items-center gap-2 mt-1">
                {mcp.approval_required ? (
                  <>
                    <LockIcon className="w-4 h-4 text-ork-amber" />
                    <span className="text-sm font-mono text-ork-amber">Yes</span>
                  </>
                ) : (
                  <>
                    <UnlockIcon className="w-4 h-4 text-ork-green" />
                    <span className="text-sm font-mono text-ork-green">No</span>
                  </>
                )}
              </div>
            </div>

            {/* Audit */}
            <div className="space-y-1">
              <span className="data-label">Audit Required</span>
              <div className="flex items-center gap-2 mt-1">
                {mcp.audit_required ? (
                  <>
                    <CheckIcon className="w-4 h-4 text-ork-purple" />
                    <span className="text-sm font-mono text-ork-purple">Yes</span>
                  </>
                ) : (
                  <>
                    <XIcon className="w-4 h-4 text-ork-dim" />
                    <span className="text-sm font-mono text-ork-dim">No</span>
                  </>
                )}
              </div>
            </div>

            {/* Allowed Agents */}
            <div className="space-y-1 w-full">
              <span className="data-label">Allowed Agents ({mcp.allowed_agents?.length ?? 0})</span>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {mcp.allowed_agents && mcp.allowed_agents.length > 0 ? (
                  mcp.allowed_agents.map((a) => (
                    <span key={a} className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono text-ork-cyan bg-ork-cyan/8 border border-ork-cyan/20 rounded">
                      {a}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-ork-dim italic font-mono">No restrictions -- all agents</span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ── 4. Contracts ─────────────────────────────────────── */}
        <div className="glass-panel p-5 space-y-4">
          <h2 className="section-title">Contracts</h2>
          <div className="space-y-3">
            <div>
              <span className="data-label">Input Contract</span>
              {mcp.input_contract_ref ? (
                <p className="font-mono text-xs text-ork-cyan mt-1 bg-ork-bg px-3 py-2 rounded border border-ork-border">
                  {mcp.input_contract_ref}
                </p>
              ) : (
                <p className="text-xs text-ork-dim italic mt-1">No contract defined</p>
              )}
            </div>
            <div>
              <span className="data-label">Output Contract</span>
              {mcp.output_contract_ref ? (
                <p className="font-mono text-xs text-ork-cyan mt-1 bg-ork-bg px-3 py-2 rounded border border-ork-border">
                  {mcp.output_contract_ref}
                </p>
              ) : (
                <p className="text-xs text-ork-dim italic mt-1">No contract defined</p>
              )}
            </div>
          </div>
        </div>

        {/* ── 5. Runtime ───────────────────────────────────────── */}
        <div className="glass-panel p-5 space-y-4">
          <h2 className="section-title">Runtime</h2>
          <div className="space-y-4">
            {/* Timeout with visual bar */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="data-label">Timeout</span>
                <span className="text-sm font-mono text-ork-text">{mcp.timeout_seconds}s</span>
              </div>
              <PercentBar value={mcp.timeout_seconds} max={120} color="cyan" />
              <p className="text-[10px] font-mono text-ork-dim mt-1">of 120s max</p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Retry Policy" mono>{mcp.retry_policy}</Field>
              <Field label="Cost Profile">
                <span className={`font-mono uppercase ${accentText(
                  mcp.cost_profile === "high" ? "red" : mcp.cost_profile === "medium" ? "amber" : mcp.cost_profile === "variable" ? "purple" : "green"
                )}`}>
                  {mcp.cost_profile}
                </span>
              </Field>
            </div>
          </div>
        </div>

        {/* ── 6. Health (prominent) ────────────────────────────── */}
        {health && (
          <div className={`glass-panel p-5 space-y-4 border-l-2 ${health.healthy ? "border-ork-green/30" : "border-ork-red/30"} lg:col-span-2`}>
            <h2 className="section-title">Health</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Healthy indicator */}
              <div className="space-y-1">
                <span className="data-label">Status</span>
                <div className="flex items-center gap-2 mt-1">
                  <span className={`glow-dot ${health.healthy ? "bg-ork-green text-ork-green" : "bg-ork-red text-ork-red"}`} />
                  <span className={`text-sm font-mono ${health.healthy ? "text-ork-green" : "text-ork-red"}`}>
                    {health.healthy ? "Healthy" : "Unhealthy"}
                  </span>
                </div>
              </div>

              {/* Total invocations */}
              <div className="space-y-1">
                <span className="data-label">Total Invocations</span>
                <p className="text-sm font-mono text-ork-text mt-1">{health.total_invocations.toLocaleString()}</p>
              </div>

              {/* Avg latency */}
              <div className="space-y-1">
                <span className="data-label">Avg Latency</span>
                <p className="text-sm font-mono text-ork-text mt-1">{health.avg_latency_ms != null ? `${health.avg_latency_ms}ms` : "--"}</p>
              </div>

              {/* Last check */}
              <div className="space-y-1">
                <span className="data-label">Last Check</span>
                <p className="text-sm font-mono text-ork-text mt-1">{fmtDate(health.last_check_at)}</p>
              </div>
            </div>

            {/* Failure rate bar */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="data-label">Failure Rate</span>
                <span className={`text-sm font-mono ${accentText(failureColor)}`}>{failureRate.toFixed(1)}%</span>
              </div>
              <PercentBar value={failureRate} max={100} color={failureColor} />
            </div>

            {/* Recent errors */}
            {health.recent_errors.length > 0 && (
              <div>
                <span className="data-label">Recent Errors</span>
                <div className="mt-2 space-y-1.5">
                  {health.recent_errors.map((err, i) => (
                    <div key={i} className="flex items-start gap-2 px-3 py-2 bg-ork-red/5 border border-ork-red/15 rounded text-xs font-mono text-ork-red/80">
                      <XIcon className="w-3 h-3 mt-0.5 shrink-0" />
                      <span>{err}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── 7. Usage ─────────────────────────────────────────── */}
        {usage && (
          <div className="glass-panel p-5 space-y-4 lg:col-span-2">
            <h2 className="section-title">Usage</h2>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="space-y-1">
                <span className="data-label">Total Invocations</span>
                <p className="text-sm font-mono text-ork-cyan mt-1">{usage.total_invocations.toLocaleString()}</p>
              </div>
              <div className="space-y-1">
                <span className="data-label">Total Cost</span>
                <p className="text-sm font-mono text-ork-amber mt-1">${usage.total_cost.toFixed(2)}</p>
              </div>
              <div className="space-y-1">
                <span className="data-label">Avg Cost / Call</span>
                <p className="text-sm font-mono text-ork-muted mt-1">${usage.avg_cost.toFixed(4)}</p>
              </div>
              <div className="space-y-1">
                <span className="data-label">Avg Latency</span>
                <p className="text-sm font-mono text-ork-muted mt-1">{usage.avg_latency_ms}ms</p>
              </div>
            </div>

            {/* Agents using */}
            <div>
              <span className="data-label">Agents Using ({usage.agents_using.length})</span>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {usage.agents_using.length > 0 ? (
                  usage.agents_using.map((a) => (
                    <span key={a} className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono text-ork-green bg-ork-green/8 border border-ork-green/20 rounded">
                      {a}
                    </span>
                  ))
                ) : (
                  <span className="text-xs text-ork-dim italic font-mono">No agents currently using this MCP</span>
                )}
              </div>
            </div>

            {/* Invocations by status */}
            {Object.keys(usage.invocations_by_status).length > 0 && (
              <div>
                <span className="data-label">Invocations by Status</span>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 mt-2">
                  {Object.entries(usage.invocations_by_status).map(([status, count]) => (
                    <div key={status} className="flex items-center justify-between px-3 py-2 bg-ork-bg border border-ork-border rounded">
                      <StatusBadge status={status} />
                      <span className="text-sm font-mono text-ork-text ml-2">{count.toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
