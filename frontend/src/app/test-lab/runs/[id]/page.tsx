"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { request } from "@/lib/api-client";
import {
  FlaskConical,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Shield,
  Target,
  FileText,
  Play,
  Send,
  Loader2,
  MessageSquare,
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

function EventDetails({ event }: { event: any }) {
  const [expanded, setExpanded] = useState(false);
  const d = event.details || {};
  const hasLlm = !!d.llm_output;
  const hasLlmReasoning = !!d.llm_reasoning;
  const hasToolCalls = d.tool_calls_planned && d.tool_calls_planned.length > 0;
  const hasToolResult = event.event_type === "tool_call_completed" && d.output_preview;
  const hasOrchestratorToolCall = event.event_type === "orchestrator_tool_call" && d.tool_name;
  const hasOrchestratorResult = event.event_type === "orchestrator_tool_result" && d.result_preview;
  const hasMcp = event.event_type === "mcp_session_connected" && d.tools;
  const hasWorkerResponse = !!d.worker_response;
  const hasLongMessage = event.message && event.message.length > 120;
  const hasSubagentPrompt = !!d.subagent && !!d.prompt;
  const hasSubagentResponse = !!d.subagent && !!d.response;
  const hasContent = hasLlm || hasLlmReasoning || hasToolCalls || hasToolResult || hasOrchestratorToolCall || hasOrchestratorResult || hasMcp || hasWorkerResponse || hasLongMessage || hasSubagentPrompt || hasSubagentResponse;

  if (!hasContent) return null;

  return (
    <div className="mt-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-[10px] font-mono text-ork-cyan/70 hover:text-ork-cyan transition-colors flex items-center gap-1"
      >
        <span className={`transition-transform ${expanded ? "rotate-90" : ""}`}>&#9654;</span>
        {expanded ? "Hide details" : "Show details"}
        {hasSubagentPrompt && <span className="text-ork-cyan/60 ml-1">Prompt</span>}
        {hasSubagentResponse && <span className="text-ork-purple/60 ml-1">LLM</span>}
        {hasWorkerResponse && <span className="text-ork-amber/60 ml-1">Agent</span>}
        {hasLlm && <span className="text-ork-purple/60 ml-1">LLM</span>}
        {hasToolCalls && <span className="text-ork-cyan/60 ml-1">Tools</span>}
        {hasToolResult && <span className="text-ork-green/60 ml-1">Result</span>}
        {hasMcp && <span className="text-ork-green/60 ml-1">MCP</span>}
      </button>

      {expanded && (
        <div className="mt-1.5 space-y-2 animate-fade-in">
          {/* SubAgent prompt (input) */}
          {hasSubagentPrompt && (
            <div className="border-l-2 border-ork-cyan/30 pl-3">
              <p className="text-[10px] font-mono text-ork-cyan mb-1 font-semibold">
                {d.subagent} — Prompt
              </p>
              <pre className="text-[10px] font-mono text-ork-muted bg-ork-bg border border-ork-border rounded p-2.5 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
{d.prompt}
              </pre>
            </div>
          )}

          {/* SubAgent response (LLM output) */}
          {hasSubagentResponse && (
            <div className="border-l-2 border-ork-purple/30 pl-3">
              <p className="text-[10px] font-mono text-ork-purple mb-1 font-semibold">
                {d.subagent} — Response
                {d.verdict && <span className="text-ork-green/70 ml-2">({d.verdict}, {d.score}/100)</span>}
              </p>
              <pre className="text-[10px] font-mono text-ork-text/80 bg-ork-bg border border-ork-border rounded p-2.5 max-h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed">
{d.response}
              </pre>
              {d.response_length && (
                <p className="text-[9px] font-mono text-ork-dim mt-1">
                  {d.response_length} chars
                </p>
              )}
            </div>
          )}

          {/* Full message if truncated */}
          {hasLongMessage && (
            <pre className="text-[10px] font-mono text-ork-muted bg-ork-bg border border-ork-border rounded p-2 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
{event.message}
            </pre>
          )}

          {/* Master orchestrator tool call */}
          {hasOrchestratorToolCall && (
            <div className="border-l-2 border-ork-purple/30 pl-3">
              <p className="text-[10px] font-mono text-ork-purple mb-1 font-semibold">Master → {d.tool_name}</p>
              {d.tool_input && (
                <pre className="text-[10px] font-mono text-ork-dim bg-ork-bg border border-ork-border rounded p-2 whitespace-pre-wrap">{d.tool_input}</pre>
              )}
              {d.llm_reasoning && (
                <pre className="text-[10px] font-mono text-ork-purple/60 mt-1 whitespace-pre-wrap">{d.llm_reasoning}</pre>
              )}
            </div>
          )}

          {/* Master orchestrator received tool result */}
          {hasOrchestratorResult && (
            <div className="border-l-2 border-ork-purple/30 pl-3">
              <p className="text-[10px] font-mono text-ork-purple mb-1 font-semibold">Master ← {d.tool_name}</p>
              <pre className="text-[10px] font-mono text-ork-text/60 bg-ork-bg border border-ork-border rounded p-2.5 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">{d.result_preview}</pre>
            </div>
          )}

          {/* LLM reasoning (from master thinking) */}
          {hasLlmReasoning && !hasOrchestratorToolCall && (
            <div className="border-l-2 border-ork-purple/20 pl-3">
              <p className="text-[10px] font-mono text-ork-purple/60 mb-1">Reasoning</p>
              <pre className="text-[10px] font-mono text-ork-text/50 whitespace-pre-wrap">{d.llm_reasoning}</pre>
            </div>
          )}

          {/* Worker agent response */}
          {hasWorkerResponse && (
            <div className="border-l-2 border-ork-amber/30 pl-3">
              <p className="text-[10px] font-mono text-ork-amber mb-1 font-semibold">Agent Response</p>
              <pre className="text-[10px] font-mono text-ork-text/80 bg-ork-bg border border-ork-border rounded p-2.5 max-h-64 overflow-y-auto whitespace-pre-wrap leading-relaxed">
{d.worker_response}
              </pre>
            </div>
          )}

          {/* LLM output */}
          {hasLlm && (
            <div className="border-l-2 border-ork-purple/30 pl-3">
              <p className="text-[10px] font-mono text-ork-purple mb-1 font-semibold">LLM Response</p>
              <pre className="text-[10px] font-mono text-ork-text/70 bg-ork-bg border border-ork-border rounded p-2.5 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
{d.llm_output}
              </pre>
            </div>
          )}

          {/* Tool calls */}
          {hasToolCalls && (
            <div className="border-l-2 border-ork-cyan/30 pl-3">
              <p className="text-[10px] font-mono text-ork-cyan mb-1 font-semibold">Tool Calls</p>
              <div className="space-y-1.5">
                {d.tool_calls_planned.map((tc: any, j: number) => (
                  <div key={j} className="bg-ork-bg border border-ork-border rounded p-2">
                    <span className="text-[10px] font-mono font-semibold text-ork-cyan">{tc.tool_name}</span>
                    {tc.tool_input && (
                      <pre className="text-[10px] font-mono text-ork-dim mt-1 whitespace-pre-wrap">{tc.tool_input}</pre>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tool result */}
          {hasToolResult && (
            <div className="border-l-2 border-ork-green/30 pl-3">
              <p className="text-[10px] font-mono text-ork-green mb-1 font-semibold">
                Tool Result {d.tool_name && d.tool_name !== "unknown" ? `— ${d.tool_name}` : ""}
              </p>
              <pre className="text-[10px] font-mono text-ork-text/60 bg-ork-bg border border-ork-border rounded p-2.5 max-h-48 overflow-y-auto whitespace-pre-wrap leading-relaxed">
{d.output_preview}
              </pre>
            </div>
          )}

          {/* MCP tools */}
          {hasMcp && (
            <div className="border-l-2 border-ork-green/30 pl-3">
              <p className="text-[10px] font-mono text-ork-green mb-1 font-semibold">MCP Tools Available</p>
              <div className="flex gap-1 flex-wrap">
                {(Array.isArray(d.tools) ? d.tools : []).map((t: string, j: number) => (
                  <span key={j} className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-ork-green/10 text-ork-green/80 border border-ork-green/20">{t}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function getAgentLabel(event: any): string | null {
  const t = event.event_type;
  const p = event.phase;
  if (t === "orchestrator_thinking") return "master (thinking)";
  if (t === "orchestrator_tool_call") return "master → worker";
  if (t === "orchestrator_tool_result") return "worker → master";
  if (t === "orchestrator_response") return "master (response)";
  if (p === "orchestrator") return "master";
  if (p === "preparation") return "preparation_agent";
  if (p === "assertions") return "assertion_agent";
  if (p === "diagnostics") return "diagnostic_agent";
  if (p === "report") return "verdict_agent";
  if (p === "runtime") {
    if (t === "agent_iteration_started" || t === "agent_iteration_completed") return "target_agent";
    if (t === "llm_request_started" || t === "llm_request_completed") return "target_agent (LLM)";
    if (t === "tool_call_started" || t === "tool_call_completed") return "target_agent (MCP)";
    if (t === "mcp_session_connected") return "MCP";
    return "runtime_adapter";
  }
  return null;
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function TestRunDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [run, setRun] = useState<any>(null);
  const [rerunning, setRerunning] = useState(false);
  const [events, setEvents] = useState<any[]>([]);
  const [assertions, setAssertions] = useState<any[]>([]);
  const [diagnostics, setDiagnostics] = useState<any[]>([]);

  // Chat with OrchestratorAgent
  const [chatMessages, setChatMessages] = useState<Array<{role: string; content: string}>>([]);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const statusRef = useRef<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!id) return;
    try {
      const [runData, eventsData, assertionsData, diagnosticsData] = await Promise.all([
        request<any>(`/api/test-lab/runs/${id}`).catch(() => null),
        request<any>(`/api/test-lab/runs/${id}/events`).catch(() => []),
        request<any>(`/api/test-lab/runs/${id}/assertions`).catch(() => []),
        request<any>(`/api/test-lab/runs/${id}/diagnostics`).catch(() => []),
      ]);
      if (runData) {
        setRun(runData);
        statusRef.current = runData.status;
      }
      setEvents(Array.isArray(eventsData) ? eventsData : eventsData?.items ?? []);
      setAssertions(Array.isArray(assertionsData) ? assertionsData : assertionsData?.items ?? []);
      setDiagnostics(Array.isArray(diagnosticsData) ? diagnosticsData : diagnosticsData?.items ?? []);
      setError(null);
    } catch (e: any) {
      setError(e.message || "Failed to load run data");
    } finally {
      setLoading(false);
    }
  }, [id]);

  // SSE streaming for live events
  useEffect(() => {
    if (!id) return;
    const evtSource = new EventSource(`/api/test-lab/runs/${id}/stream`);
    evtSource.onmessage = (msg) => {
      try {
        const evt = JSON.parse(msg.data);
        if (evt.event_type === "stream_end") {
          setRun((prev: any) => prev ? { ...prev, status: evt.status, verdict: evt.verdict, score: evt.score, summary: evt.summary } : prev);
          statusRef.current = evt.status;
          evtSource.close();
          // Final fetch to get assertions + diagnostics
          fetchData();
          return;
        }
        setEvents((prev) => {
          if (prev.some((e: any) => e.id === evt.id)) return prev;
          return [...prev, evt];
        });
      } catch { /* ignore parse errors */ }
    };
    evtSource.onerror = () => { evtSource.close(); };
    return () => evtSource.close();
  }, [id, fetchData]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      if (statusRef.current === "running" || statusRef.current === "queued" || statusRef.current === null) {
        fetchData();
      }
    }, 10000); // Slower polling since SSE handles live updates
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
  const isLive = run?.status === "running" || run?.status === "queued";

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
        {run?.scenario_id && run?.status !== "running" && run?.status !== "queued" && (
          <button
            disabled={rerunning}
            onClick={async () => {
              setRerunning(true);
              try {
                const newRun = await request<{ id: string }>(`/api/test-lab/scenarios/${run.scenario_id}/run`, { method: "POST" });
                router.push(`/test-lab/runs/${newRun.id}`);
              } catch { /* ignore */ }
              finally { setRerunning(false); }
            }}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider rounded border bg-ork-cyan/10 text-ork-cyan border-ork-cyan/30 hover:bg-ork-cyan/20 transition-colors disabled:opacity-40"
          >
            <Play size={13} /> {rerunning ? "Running..." : "Re-run"}
          </button>
        )}
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
        <h2 className="section-title mb-4 flex items-center gap-2">
          <Clock size={13} />
          Execution Timeline ({events.length} events)
          {isLive && <span className="w-2 h-2 rounded-full bg-ork-green animate-pulse ml-2" title="Live" />}
        </h2>
        <div className="glass-panel p-5 max-h-[600px] overflow-y-auto">
          {events.length === 0 ? (
            <div className="text-center py-8">
              {isLive ? (
                <div className="flex flex-col items-center gap-2">
                  <div className="w-5 h-5 border-2 border-ork-cyan border-t-transparent rounded-full animate-spin" />
                  <p className="text-ork-cyan font-mono text-xs">Waiting for events...</p>
                </div>
              ) : (
                <p className="text-ork-muted font-mono text-xs">No timeline events</p>
              )}
            </div>
          ) : (
            <div className="space-y-0">
              {events.map((event: any, i: number) => {
                const phase = event.phase || "unknown";
                const phaseColor = PHASE_COLORS[phase] || "text-ork-muted border-ork-border bg-ork-surface";
                const dotColor = PHASE_DOT_COLORS[phase] || "bg-ork-dim";
                const isLastEvent = i === events.length - 1;
                const isActive = isLastEvent && isLive;
                const agentName = getAgentLabel(event);

                return (
                  <div key={event.id || i} className={`flex items-start gap-3 ${isActive ? "animate-fade-in" : ""}`}>
                    {/* Timeline dot + connector */}
                    <div className="flex flex-col items-center pt-1.5">
                      {isActive ? (
                        <div className="w-3 h-3 rounded-full bg-ork-cyan animate-pulse" style={{ boxShadow: "0 0 8px rgba(0,212,255,0.5)" }} />
                      ) : (
                        <div className={`w-2 h-2 rounded-full ${dotColor}`} />
                      )}
                      {!isLastEvent && <div className="w-px flex-1 min-h-[20px] border-l border-dashed border-ork-border" />}
                    </div>

                    {/* Event content */}
                    <div className="flex-1 pb-3">
                      <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                        <span className={`text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded border ${phaseColor}`}>{phase}</span>
                        <span className="text-[10px] font-mono text-ork-cyan">{event.event_type}</span>
                        {agentName && (
                          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-ork-purple/10 text-ork-purple border border-ork-purple/20">
                            {agentName}
                          </span>
                        )}
                        {event.duration_ms != null && (
                          <span className="text-[10px] font-mono text-ork-amber">{formatDuration(event.duration_ms)}</span>
                        )}
                        <span className="text-[10px] font-mono text-ork-dim ml-auto">{formatTimestamp(event.timestamp)}</span>
                      </div>
                      <p className="text-xs text-ork-muted">
                        {event.message && event.message.length > 120
                          ? event.message.slice(0, 120) + "..."
                          : event.message}
                      </p>

                      {/* Expandable details */}
                      <EventDetails event={event} />

                      {/* Spinner for active event */}
                      {isActive && (
                        <div className="mt-2 flex items-center gap-2">
                          <div className="w-3 h-3 border border-ork-cyan border-t-transparent rounded-full animate-spin" />
                          <span className="text-[10px] font-mono text-ork-cyan animate-pulse">Agent working...</span>
                        </div>
                      )}
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
          <p className="text-xs font-mono text-ork-muted whitespace-pre-wrap">{run.summary}</p>
        </div>
      )}

      {/* ── Chat with OrchestratorAgent ── */}
      {run && (run.status === "completed" || run.status === "failed") && (
        <div>
          <h2 className="section-title mb-4 flex items-center gap-2">
            <MessageSquare size={13} />
            Chat with OrchestratorAgent
          </h2>
          <div className="glass-panel overflow-hidden">
            {/* Messages */}
            <div className="max-h-[400px] overflow-y-auto p-4 space-y-3">
              {chatMessages.length === 0 && (
                <p className="text-center text-xs font-mono text-ork-dim py-8">
                  Ask the orchestrator about the results, request a deeper analysis, or ask for a follow-up test.
                </p>
              )}
              {chatMessages.map((msg, i) => (
                <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[80%] rounded-lg px-4 py-2.5 ${
                    msg.role === "user"
                      ? "bg-ork-cyan/10 border border-ork-cyan/30 rounded-tr-sm"
                      : "bg-ork-surface border border-ork-dim/20 rounded-tl-sm"
                  }`}>
                    <p className={`text-[10px] font-mono mb-1 uppercase tracking-wider ${
                      msg.role === "user" ? "text-ork-cyan/60" : "text-ork-purple/60"
                    }`}>
                      {msg.role === "user" ? "you" : "orchestrator"}
                    </p>
                    <p className="text-sm text-ork-muted leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                  </div>
                </div>
              ))}
              {chatLoading && (
                <div className="flex justify-start">
                  <div className="bg-ork-surface border border-ork-dim/20 rounded-lg px-4 py-3 flex items-center gap-2">
                    <Loader2 size={13} className="text-ork-cyan animate-spin" />
                    <span className="text-xs font-mono text-ork-dim animate-pulse">Thinking...</span>
                  </div>
                </div>
              )}
              <div ref={chatBottomRef} />
            </div>

            {/* Input */}
            <div className="border-t border-ork-border/50 p-3 flex items-end gap-2">
              <textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (!chatInput.trim() || chatLoading) return;
                    const msg = chatInput.trim();
                    setChatInput("");
                    setChatMessages(prev => [...prev, { role: "user", content: msg }]);
                    setChatLoading(true);
                    request<{ response: string }>(`/api/test-lab/runs/${id}/chat`, {
                      method: "POST",
                      body: JSON.stringify({ message: msg }),
                    })
                      .then(data => {
                        setChatMessages(prev => [...prev, { role: "orchestrator", content: data.response }]);
                      })
                      .catch(err => {
                        setChatMessages(prev => [...prev, { role: "orchestrator", content: `Error: ${err.message}` }]);
                      })
                      .finally(() => {
                        setChatLoading(false);
                        setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
                      });
                  }
                }}
                placeholder="Ask the orchestrator... (e.g., 'explain the verdict', 'run a stricter test', 'check policy compliance')"
                disabled={chatLoading}
                rows={1}
                className="flex-1 resize-none bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim/50 focus:outline-none focus:border-ork-cyan/40 disabled:opacity-50 min-h-[38px] max-h-[100px] overflow-y-auto"
              />
              <button
                onClick={() => {
                  if (!chatInput.trim() || chatLoading) return;
                  const msg = chatInput.trim();
                  setChatInput("");
                  setChatMessages(prev => [...prev, { role: "user", content: msg }]);
                  setChatLoading(true);
                  request<{ response: string }>(`/api/test-lab/runs/${id}/chat`, {
                    method: "POST",
                    body: JSON.stringify({ message: msg }),
                  })
                    .then(data => {
                      setChatMessages(prev => [...prev, { role: "orchestrator", content: data.response }]);
                    })
                    .catch(err => {
                      setChatMessages(prev => [...prev, { role: "orchestrator", content: `Error: ${err.message}` }]);
                    })
                    .finally(() => {
                      setChatLoading(false);
                      setTimeout(() => chatBottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
                    });
                }}
                disabled={chatLoading || !chatInput.trim()}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-cyan/15 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/25 transition-colors disabled:opacity-40 flex-shrink-0"
              >
                {chatLoading ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                Send
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
