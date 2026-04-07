"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  FlaskConical,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Shield,
  Target,
  FileText,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

const PHASE_COLORS: Record<string, string> = {
  orchestrator: "text-ork-purple border-ork-purple/30 bg-ork-purple/10",
  runtime: "text-ork-cyan border-ork-cyan/30 bg-ork-cyan/10",
  preparation: "text-ork-purple border-ork-purple/30 bg-ork-purple/10",
  assertions: "text-ork-green border-ork-green/30 bg-ork-green/10",
  diagnostics: "text-ork-amber border-ork-amber/30 bg-ork-amber/10",
  report: "text-ork-cyan border-ork-cyan/30 bg-ork-cyan/10",
};

const PHASE_DOT_COLORS: Record<string, string> = {
  orchestrator: "bg-ork-purple",
  runtime: "bg-ork-cyan",
  preparation: "bg-ork-purple",
  assertions: "bg-ork-green",
  diagnostics: "bg-ork-amber",
  report: "bg-ork-cyan",
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "text-ork-red bg-ork-red/15 border-ork-red/30",
  error: "text-ork-red bg-ork-red/10 border-ork-red/20",
  warning: "text-ork-amber bg-ork-amber/10 border-ork-amber/20",
  info: "text-ork-cyan bg-ork-cyan/10 border-ork-cyan/20",
};

const VERDICT_DISPLAY: Record<string, { label: string; color: string; icon: "pass" | "fail" | "warn" }> = {
  passed: { label: "PASSED", color: "text-ork-green", icon: "pass" },
  passed_with_warnings: { label: "PASSED WITH WARNINGS", color: "text-ork-amber", icon: "warn" },
  failed: { label: "FAILED", color: "text-ork-red", icon: "fail" },
};

function formatDate(iso: string | null) {
  if (!iso) return "--";
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
}

function formatTimestamp(iso: string) {
  return new Date(iso).toLocaleTimeString("en-US", {
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
}

function formatDuration(ms: number | null | undefined) {
  if (ms == null) return "--";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function TestRunDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [run, setRun] = useState<any>(null);
  const [events, setEvents] = useState<any[]>([]);
  const [assertions, setAssertions] = useState<any[]>([]);
  const [diagnostics, setDiagnostics] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const statusRef = useRef<string | null>(null);

  const fetchData = useCallback(() => {
    if (!id) return;
    Promise.all([
      fetch(`/api/test-lab/runs/${id}`).then((r) => r.ok ? r.json() : null),
      fetch(`/api/test-lab/runs/${id}/events`).then((r) => r.ok ? r.json() : []),
      fetch(`/api/test-lab/runs/${id}/assertions`).then((r) => r.ok ? r.json() : []),
      fetch(`/api/test-lab/runs/${id}/diagnostics`).then((r) => r.ok ? r.json() : []),
    ])
      .then(([runData, eventsData, assertionsData, diagnosticsData]) => {
        if (runData) {
          setRun(runData);
          statusRef.current = runData.status;
        }
        setEvents(eventsData || []);
        setAssertions(assertionsData || []);
        setDiagnostics(diagnosticsData || []);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      if (statusRef.current === "running" || statusRef.current === "queued" || statusRef.current === null) {
        fetchData();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-16 text-center">
          <div className="text-ork-cyan font-mono text-sm animate-pulse">Loading run data...</div>
        </div>
      </div>
    );
  }

  if (error && !run) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-8 text-center">
          <p className="text-ork-red font-mono text-sm">Error: {error}</p>
          <Link href="/test-lab" className="text-ork-cyan text-xs font-mono mt-3 inline-block hover:underline">Back to Test Lab</Link>
        </div>
      </div>
    );
  }

  const passedAssertions = assertions.filter((a: any) => a.passed).length;
  const totalAssertions = assertions.length;
  const verdictInfo = run?.verdict ? VERDICT_DISPLAY[run.verdict] : null;

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/test-lab" className="text-ork-muted hover:text-ork-cyan transition-colors text-xs font-mono">TEST LAB /</Link>
          <div>
            <div className="flex items-center gap-3">
              <FlaskConical size={16} className="text-ork-purple" />
              <h1 className="font-mono text-sm tracking-wide text-ork-text">Run {id?.slice(0, 16)}...</h1>
              {run && <StatusBadge status={run.status} />}
              {verdictInfo && (
                <span className={`flex items-center gap-1 text-xs font-mono font-semibold ${verdictInfo.color}`}>
                  {verdictInfo.icon === "pass" && <CheckCircle size={14} />}
                  {verdictInfo.icon === "warn" && <AlertTriangle size={14} />}
                  {verdictInfo.icon === "fail" && <XCircle size={14} />}
                  {verdictInfo.label}
                </span>
              )}
            </div>
            <p className="text-[10px] text-ork-dim font-mono mt-0.5">Agent: {run?.agent_id} &middot; v{run?.agent_version}</p>
          </div>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-4">
        <div className="glass-panel p-3">
          <p className="data-label">Score</p>
          <p className={`font-mono text-2xl font-semibold mt-1 ${
            run?.score != null
              ? run.score >= 80 ? "text-ork-green" : run.score >= 50 ? "text-ork-amber" : "text-ork-red"
              : "text-ork-dim"
          }`}>
            {run?.score != null ? `${run.score}/100` : "--"}
          </p>
        </div>
        <div className="glass-panel p-3">
          <p className="data-label">Duration</p>
          <p className="font-mono text-2xl font-semibold text-ork-text mt-1">{formatDuration(run?.duration_ms)}</p>
        </div>
        <div className="glass-panel p-3">
          <p className="data-label">Assertions</p>
          <p className="font-mono text-2xl font-semibold text-ork-text mt-1">
            <span className={passedAssertions === totalAssertions && totalAssertions > 0 ? "text-ork-green" : "text-ork-amber"}>{passedAssertions}</span>
            <span className="text-ork-dim text-lg"> / {totalAssertions}</span>
          </p>
        </div>
        <div className="glass-panel p-3">
          <p className="data-label">Timeline</p>
          <p className="font-mono text-sm text-ork-muted mt-1">{formatDate(run?.started_at)} &rarr; {formatDate(run?.ended_at)}</p>
        </div>
      </div>

      {/* Error Message */}
      {run?.error_message && (
        <div className="glass-panel p-4 border-ork-red/30 bg-ork-red/5">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle size={14} className="text-ork-red" />
            <p className="data-label text-ork-red">Error</p>
          </div>
          <pre className="text-xs font-mono text-ork-red/80 whitespace-pre-wrap">{run.error_message}</pre>
        </div>
      )}

      {/* Execution Timeline */}
      <div>
        <h2 className="section-title mb-4 flex items-center gap-2"><Clock size={13} /> Execution Timeline ({events.length} events)</h2>
        <div className="glass-panel p-5">
          {events.length === 0 ? (
            <p className="text-ork-muted font-mono text-xs text-center py-8">
              {run?.status === "running" || run?.status === "queued" ? "Waiting for events..." : "No timeline events"}
            </p>
          ) : (
            <div className="space-y-0">
              {events.map((event: any, i: number) => {
                const phase = event.phase || "unknown";
                const phaseColor = PHASE_COLORS[phase] || "text-ork-muted border-ork-border bg-ork-surface";
                const dotColor = PHASE_DOT_COLORS[phase] || "bg-ork-dim";
                return (
                  <div key={event.id || i} className="flex items-start gap-3">
                    <div className="flex flex-col items-center pt-1.5">
                      <div className={`w-2 h-2 rounded-full ${dotColor}`} />
                      {i < events.length - 1 && <div className="w-px flex-1 min-h-[20px] border-l border-dashed border-ork-border" />}
                    </div>
                    <div className="flex-1 pb-3">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span className={`text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${phaseColor}`}>{phase}</span>
                        <span className="text-[10px] font-mono text-ork-cyan">{event.event_type}</span>
                        {event.duration_ms != null && (
                          <span className="text-[10px] font-mono text-ork-amber">{formatDuration(event.duration_ms)}</span>
                        )}
                        <span className="text-[10px] font-mono text-ork-dim ml-auto">{formatTimestamp(event.timestamp)}</span>
                      </div>
                      <p className="text-xs text-ork-muted">{event.message}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Assertions Panel */}
      {assertions.length > 0 && (
        <div>
          <h2 className="section-title mb-4 flex items-center gap-2"><Target size={13} /> Assertion Results</h2>
          <div className="glass-panel overflow-hidden">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ork-border">
                  <th className="data-label text-left px-4 py-2.5 w-10">Pass</th>
                  <th className="data-label text-left px-4 py-2.5">Type</th>
                  <th className="data-label text-left px-4 py-2.5">Target</th>
                  <th className="data-label text-left px-4 py-2.5">Expected</th>
                  <th className="data-label text-left px-4 py-2.5">Actual</th>
                  <th className="data-label text-left px-4 py-2.5">Message</th>
                </tr>
              </thead>
              <tbody>
                {assertions.map((a: any, i: number) => (
                  <tr key={a.id || i} className={`border-b border-ork-border/50 ${a.passed ? "" : "bg-ork-red/5"}`}>
                    <td className="px-4 py-2.5 text-center">
                      {a.passed ? <CheckCircle size={14} className="text-ork-green" /> : <XCircle size={14} className="text-ork-red" />}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-text">{a.assertion_type}</td>
                    <td className="px-4 py-2.5 font-mono text-ork-muted">{a.target || "--"}</td>
                    <td className="px-4 py-2.5 font-mono text-ork-muted max-w-[150px] truncate">{a.expected || "--"}</td>
                    <td className="px-4 py-2.5 font-mono text-ork-muted max-w-[150px] truncate">{a.actual || "--"}</td>
                    <td className="px-4 py-2.5 text-ork-muted max-w-[200px] truncate">{a.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Diagnostics Panel */}
      {diagnostics.length > 0 && (
        <div>
          <h2 className="section-title mb-4 flex items-center gap-2"><Shield size={13} /> Diagnostics ({diagnostics.length})</h2>
          <div className="space-y-3">
            {diagnostics.map((d: any, i: number) => {
              const sevColor = SEVERITY_COLORS[d.severity] || SEVERITY_COLORS.info;
              return (
                <div key={d.id || i} className="glass-panel p-4">
                  <div className="flex items-center gap-3 mb-2">
                    <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${sevColor}`}>{d.severity}</span>
                    <span className="text-xs font-mono text-ork-cyan">{d.code}</span>
                  </div>
                  <p className="text-sm text-ork-text mb-2">{d.message}</p>
                  {d.probable_causes && d.probable_causes.length > 0 && (
                    <div className="mt-2">
                      <p className="data-label mb-1">Probable Causes</p>
                      <ul className="list-disc list-inside space-y-0.5">
                        {d.probable_causes.map((cause: string, ci: number) => (
                          <li key={ci} className="text-xs text-ork-muted font-mono">{cause}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {d.recommendation && (
                    <div className="mt-2">
                      <p className="data-label mb-1">Recommendation</p>
                      <p className="text-xs text-ork-amber font-mono">{d.recommendation}</p>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Final Output */}
      {run?.final_output && (
        <div>
          <h2 className="section-title mb-4 flex items-center gap-2"><FileText size={13} /> Final Output</h2>
          <div className="glass-panel p-0 overflow-hidden">
            <pre className="p-5 text-xs font-mono text-ork-muted whitespace-pre-wrap max-h-[500px] overflow-y-auto leading-relaxed">{run.final_output}</pre>
          </div>
        </div>
      )}

      {/* Summary */}
      {run?.summary && (
        <div className="glass-panel p-4">
          <p className="text-xs font-mono text-ork-muted">{run.summary}</p>
        </div>
      )}
    </div>
  );
}
