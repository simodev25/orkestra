"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  FlaskConical, Play, Eye, Plus, Settings, Send, ChevronDown, Loader2,
  MessageSquare, List,
} from "lucide-react";
import { request } from "@/lib/api-client";
import { listAgents } from "@/lib/agent-registry/service";
import type { AgentDefinition } from "@/lib/agent-registry/types";

// ─── Types ──────────────────────────────────────────────────────────────────

interface Scenario {
  id: string;
  name: string;
  agent_id: string;
  description?: string;
  input_prompt?: string;
  timeout_seconds: number;
  max_iterations: number;
  assertions: any[];
  expected_tools?: string[];
  tags: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

interface ConversationMessage {
  role: "user" | "orchestrator" | "system";
  content: string;
  metadata?: Record<string, unknown>;
}

interface SessionState {
  session_id: string;
  target_agent_id: string | null;
  target_agent_label: string | null;
  current_status: "idle" | "running" | "awaiting_user" | "completed";
  last_verdict: string | null;
  last_score: number | null;
  last_run_id: string | null;
  recent_run_ids: string[];
  available_followups: string[];
  conversation: ConversationMessage[];
}

interface SessionResponse {
  session: SessionState;
  last_response: string | null;
}

// ─── Constants ──────────────────────────────────────────────────────────────

const FOLLOWUP_LABELS: Record<string, string> = {
  stricter: "Plus strict",
  robustness: "Edge case",
  policy: "Test policy",
  rerun: "Rejouer",
  targeted: "Test cible",
  performance: "Performance",
  tool_usage: "Usage outils",
  compare: "Comparer",
};

const FOLLOWUP_MESSAGES: Record<string, string> = {
  stricter: "Run a stricter version",
  robustness: "Run an edge case test",
  policy: "Test policy compliance",
  rerun: "Rerun the last test",
  targeted: "Run a targeted test",
  performance: "Run a performance test",
  tool_usage: "Test tool usage patterns",
  compare: "Compare with baseline",
};

// ─── Helpers ────────────────────────────────────────────────────────────────

function renderContent(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={i} className="text-ork-text font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    return <span key={i}>{part}</span>;
  });
}

function VerdictBadge({ verdict }: { verdict: string | null }) {
  if (!verdict) return null;
  const colorMap: Record<string, string> = {
    passed: "text-ork-green border-ork-green/30 bg-ork-green/10",
    failed: "text-ork-red border-ork-red/30 bg-ork-red/10",
    warning: "text-ork-amber border-ork-amber/30 bg-ork-amber/10",
  };
  const cls = colorMap[verdict.toLowerCase()] ?? "text-ork-dim border-ork-border bg-ork-surface";
  return (
    <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${cls}`}>
      {verdict}
    </span>
  );
}

// ═════════════════════════════════════════════════════════════════════════════
// Main Page
// ═════════════════════════════════════════════════════════════════════════════

export default function TestLabPage() {
  const router = useRouter();
  const [tab, setTab] = useState<"scenarios" | "interactive">("interactive");

  // ─── Scenarios state ────────────────────────────────────────────────────
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenariosLoading, setScenariosLoading] = useState(true);
  const [scenariosError, setScenariosError] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  // ─── Chat state ─────────────────────────────────────────────────────────
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [chatStatus, setChatStatus] = useState<"idle" | "running" | "awaiting_user" | "completed">("idle");
  const [targetAgent, setTargetAgent] = useState<{ id: string; label: string } | null>(null);
  const [availableFollowups, setAvailableFollowups] = useState<string[]>([]);
  const [lastVerdict, setLastVerdict] = useState<string | null>(null);
  const [lastScore, setLastScore] = useState<number | null>(null);
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);

  const chatBottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // ─── Fetch scenarios ────────────────────────────────────────────────────
  const fetchScenarios = useCallback(() => {
    setScenariosLoading(true);
    fetch("/api/test-lab/scenarios")
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText);
        return res.json();
      })
      .then((data) => {
        const items = Array.isArray(data) ? data : data.items ?? [];
        setScenarios(items);
        setScenariosError(null);
      })
      .catch((e) => setScenariosError(e.message))
      .finally(() => setScenariosLoading(false));
  }, []);

  useEffect(() => {
    fetchScenarios();
  }, [fetchScenarios]);

  // ─── Chat: auto-scroll ──────────────────────────────────────────────────
  useEffect(() => {
    if (tab === "interactive") {
      chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [conversation, chatStatus, tab]);

  // ─── Chat: close dropdown on outside click ──────────────────────────────
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // ─── Chat: apply session ────────────────────────────────────────────────
  const applySession = useCallback((sess: SessionState) => {
    setConversation(sess.conversation ?? []);
    setChatStatus(sess.current_status);
    setAvailableFollowups(sess.available_followups ?? []);
    setLastVerdict(sess.last_verdict);
    setLastScore(sess.last_score);
    if (sess.target_agent_id) {
      setTargetAgent({ id: sess.target_agent_id, label: sess.target_agent_label ?? sess.target_agent_id });
    }
  }, []);

  // ─── Chat: init session ─────────────────────────────────────────────────
  useEffect(() => {
    async function initChat() {
      try {
        const [agentList, sessResp] = await Promise.all([
          listAgents(),
          request<SessionResponse>("/api/test-lab/sessions", { method: "POST", body: JSON.stringify({}) }),
        ]);
        setAgents(agentList);
        setSessionId(sessResp.session.session_id);
        applySession(sessResp.session);
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : "Failed to initialize session";
        setConversation([{ role: "system", content: `Error: ${msg}` }]);
      }
    }
    void initChat();
  }, [applySession]);

  // ─── Chat: send message ─────────────────────────────────────────────────
  const sendMessage = useCallback(async (text: string) => {
    if (!sessionId || !text.trim() || chatLoading) return;
    setChatLoading(true);
    setChatInput("");
    setConversation((prev) => [...prev, { role: "user", content: text.trim() }]);
    try {
      const resp = await request<SessionResponse>(`/api/test-lab/sessions/${sessionId}/message`, {
        method: "POST",
        body: JSON.stringify({ message: text.trim() }),
      });
      applySession(resp.session);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Request failed";
      setConversation((prev) => [...prev, { role: "system", content: `Error: ${msg}` }]);
      setChatStatus("awaiting_user");
    } finally {
      setChatLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [sessionId, chatLoading, applySession]);

  const handleSelectAgent = useCallback(async (agent: AgentDefinition) => {
    setSelectedAgentId(agent.id);
    setDropdownOpen(false);
    await sendMessage(`use ${agent.id}`);
  }, [sendMessage]);

  const handleFollowup = useCallback((key: string) => {
    void sendMessage(FOLLOWUP_MESSAGES[key] ?? key);
  }, [sendMessage]);

  const handleNewSession = useCallback(async () => {
    setChatLoading(true);
    setSelectedAgentId("");
    setTargetAgent(null);
    setAvailableFollowups([]);
    setLastVerdict(null);
    setLastScore(null);
    try {
      const resp = await request<SessionResponse>("/api/test-lab/sessions", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setSessionId(resp.session.session_id);
      applySession(resp.session);
    } catch (e: unknown) {
      setConversation([{ role: "system", content: `Error: ${e instanceof Error ? e.message : "Failed"}` }]);
    } finally {
      setChatLoading(false);
    }
  }, [applySession]);

  function handleChatKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage(chatInput);
    }
  }

  // ─── Scenarios: run handler ─────────────────────────────────────────────
  async function handleRun(scenarioId: string) {
    setRunningId(scenarioId);
    try {
      const res = await fetch(`/api/test-lab/scenarios/${scenarioId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || res.statusText);
      }
      const run = await res.json();
      router.push(`/test-lab/runs/${run.id}`);
    } catch (e: any) {
      setScenariosError(e.message);
    } finally {
      setRunningId(null);
    }
  }

  const selectedAgent = agents.find((a) => a.id === selectedAgentId);

  // ═══════════════════════════════════════════════════════════════════════════
  // Render
  // ═══════════════════════════════════════════════════════════════════════════

  return (
    <div className="flex flex-col h-[calc(100vh-0px)]">
      {/* ── Header ── */}
      <div className="flex-shrink-0 px-6 pt-6 pb-0">
        <div className="max-w-[1200px] mx-auto">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <FlaskConical size={18} className="text-ork-purple" />
              <h1 className="font-mono text-sm tracking-wide text-ork-text uppercase">
                Agentic Test Lab
              </h1>
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/test-lab/scenarios/new"
                className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-cyan/15 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/25 transition-colors"
              >
                <Plus size={13} />
                Create Scenario
              </Link>
              <Link
                href="/test-lab/config"
                className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-surface text-ork-muted border border-ork-border rounded hover:text-ork-text hover:border-ork-dim transition-colors"
              >
                <Settings size={13} />
                Config
              </Link>
            </div>
          </div>

          {/* ── Tabs ── */}
          <div className="flex gap-0 border-b border-ork-border">
            <button
              onClick={() => setTab("interactive")}
              className={`flex items-center gap-2 px-5 py-2.5 text-xs font-mono uppercase tracking-wider border-b-2 transition-colors ${
                tab === "interactive"
                  ? "border-ork-purple text-ork-purple"
                  : "border-transparent text-ork-dim hover:text-ork-muted"
              }`}
            >
              <MessageSquare size={13} />
              Interactive Session
            </button>
            <button
              onClick={() => setTab("scenarios")}
              className={`flex items-center gap-2 px-5 py-2.5 text-xs font-mono uppercase tracking-wider border-b-2 transition-colors ${
                tab === "scenarios"
                  ? "border-ork-cyan text-ork-cyan"
                  : "border-transparent text-ork-dim hover:text-ork-muted"
              }`}
            >
              <List size={13} />
              Scenarios
            </button>
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* Tab: Interactive Session                                               */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {tab === "interactive" && (
        <div className="flex-1 flex flex-col min-h-0">
          {/* ── Agent bar ── */}
          <div className="flex-shrink-0 border-b border-ork-border/30 bg-ork-surface/30 px-6 py-2.5">
            <div className="max-w-[1200px] mx-auto flex items-center gap-3 flex-wrap">
              {/* Agent dropdown */}
              <div className="relative" ref={dropdownRef}>
                <button
                  onClick={() => setDropdownOpen((v) => !v)}
                  disabled={chatLoading}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-surface border border-ork-border rounded hover:border-ork-dim transition-colors disabled:opacity-50 min-w-[180px]"
                >
                  <span className="flex-1 text-left truncate text-ork-muted">
                    {selectedAgent ? selectedAgent.name : "Select Agent"}
                  </span>
                  <ChevronDown size={11} className={`text-ork-dim transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
                </button>
                {dropdownOpen && (
                  <div className="absolute top-full left-0 mt-1 z-50 glass-panel min-w-[240px] max-h-64 overflow-y-auto shadow-xl">
                    {agents.length === 0 ? (
                      <p className="text-xs font-mono text-ork-dim px-3 py-2">No agents available</p>
                    ) : (
                      agents.map((a) => (
                        <button
                          key={a.id}
                          onClick={() => void handleSelectAgent(a)}
                          className={`w-full text-left px-3 py-2 text-xs font-mono hover:bg-ork-hover/40 transition-colors ${
                            a.id === selectedAgentId ? "text-ork-cyan" : "text-ork-muted"
                          }`}
                        >
                          <span className="block text-ork-text">{a.name}</span>
                          <span className="block text-[10px] text-ork-dim">{a.id}</span>
                        </button>
                      ))
                    )}
                  </div>
                )}
              </div>

              {/* New session */}
              <button
                onClick={() => void handleNewSession()}
                disabled={chatLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-surface text-ork-muted border border-ork-border rounded hover:text-ork-text hover:border-ork-dim transition-colors disabled:opacity-50"
              >
                <Plus size={11} />
                New Session
              </button>

              {/* Status indicators */}
              <div className="flex items-center gap-3 ml-auto text-[10px] font-mono text-ork-dim">
                {targetAgent && (
                  <span>Agent: <span className="text-ork-cyan">{targetAgent.label}</span></span>
                )}
                {lastVerdict && <VerdictBadge verdict={lastVerdict} />}
                {lastScore !== null && (
                  <span>
                    Score:{" "}
                    <span className={lastScore >= 80 ? "text-ork-green" : lastScore >= 50 ? "text-ork-amber" : "text-ork-red"}>
                      {lastScore}/100
                    </span>
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* ── Chat messages ── */}
          <div className="flex-1 overflow-y-auto px-6 py-4">
            <div className="max-w-[900px] mx-auto space-y-4">
              {conversation.length === 0 && (
                <div className="text-center py-16">
                  <FlaskConical size={32} className="text-ork-purple/30 mx-auto mb-4" />
                  <p className="text-ork-dim text-xs font-mono">
                    Select an agent and describe what you want to test.
                  </p>
                  <p className="text-ork-dim/50 text-[10px] font-mono mt-1">
                    Example: "Test summary_agent on a COMEX cyber-risk case"
                  </p>
                </div>
              )}

              {conversation.map((msg, idx) => {
                const isLastOrchMsg =
                  msg.role === "orchestrator" &&
                  idx === conversation.map((m) => m.role).lastIndexOf("orchestrator");

                return (
                  <div key={idx}>
                    {msg.role === "system" && (
                      <div className="flex justify-center">
                        <p className="text-ork-dim italic text-xs font-mono px-4 py-1.5">{msg.content}</p>
                      </div>
                    )}
                    {msg.role === "user" && (
                      <div className="flex justify-end">
                        <div className="max-w-[75%] bg-ork-cyan/10 border border-ork-cyan/30 rounded-lg rounded-tr-sm px-4 py-2.5">
                          <p className="text-[10px] font-mono text-ork-cyan/60 mb-1 uppercase tracking-wider">you</p>
                          <p className="text-sm text-ork-text leading-relaxed">{msg.content}</p>
                        </div>
                      </div>
                    )}
                    {msg.role === "orchestrator" && (
                      <div className="flex justify-start">
                        <div className="max-w-[80%] bg-ork-surface border border-ork-dim/20 rounded-lg rounded-tl-sm px-4 py-2.5">
                          <p className="text-[10px] font-mono text-ork-purple/70 mb-1.5 uppercase tracking-wider">orchestrator</p>
                          <div className="text-sm text-ork-muted leading-relaxed whitespace-pre-wrap">
                            {renderContent(msg.content)}
                          </div>
                          {isLastOrchMsg && availableFollowups.length > 0 && !chatLoading && (
                            <div className="mt-3 pt-3 border-t border-ork-border/30 flex flex-wrap gap-2">
                              {availableFollowups.map((key) => (
                                <button
                                  key={key}
                                  onClick={() => handleFollowup(key)}
                                  className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider border border-ork-cyan/25 text-ork-cyan/70 bg-ork-cyan/5 rounded hover:bg-ork-cyan/15 hover:text-ork-cyan hover:border-ork-cyan/40 transition-colors"
                                >
                                  {FOLLOWUP_LABELS[key] ?? key}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}

              {(chatLoading || chatStatus === "running") && (
                <div className="flex justify-start">
                  <div className="bg-ork-surface border border-ork-dim/20 rounded-lg rounded-tl-sm px-4 py-3 flex items-center gap-2">
                    <Loader2 size={13} className="text-ork-cyan animate-spin" />
                    <span className="text-xs font-mono text-ork-dim animate-pulse">
                      {chatStatus === "running" ? "Running test..." : "Processing..."}
                    </span>
                  </div>
                </div>
              )}

              <div ref={chatBottomRef} />
            </div>
          </div>

          {/* ── Input bar ── */}
          <div className="flex-shrink-0 border-t border-ork-border/60 bg-ork-surface/50 backdrop-blur px-6 py-3">
            <div className="max-w-[900px] mx-auto flex items-end gap-3">
              <textarea
                ref={inputRef}
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={handleChatKeyDown}
                placeholder={!sessionId ? "Initializing..." : !targetAgent ? "Select an agent or type: Test [agent_id] on [objective]" : "Describe your test..."}
                disabled={chatLoading || !sessionId}
                rows={1}
                className="flex-1 resize-none bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim/50 focus:outline-none focus:border-ork-cyan/40 transition-colors disabled:opacity-50 min-h-[38px] max-h-[120px] overflow-y-auto"
                style={{ height: "auto" }}
                onInput={(e) => {
                  const el = e.currentTarget;
                  el.style.height = "auto";
                  el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
                }}
              />
              <button
                onClick={() => void sendMessage(chatInput)}
                disabled={chatLoading || !chatInput.trim() || !sessionId}
                className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-cyan/15 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
              >
                {chatLoading ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                Send
              </button>
            </div>
            <p className="max-w-[900px] mx-auto mt-1 text-[10px] font-mono text-ork-dim/40">
              Enter to send · Shift+Enter for newline · Click follow-up buttons for suggested next steps
            </p>
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {/* Tab: Scenarios                                                         */}
      {/* ═══════════════════════════════════════════════════════════════════════ */}
      {tab === "scenarios" && (
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="max-w-[1200px] mx-auto space-y-6">
            {scenariosError && (
              <div className="glass-panel p-3 border-ork-red/30 bg-ork-red/5">
                <p className="text-ork-red text-xs font-mono">{scenariosError}</p>
              </div>
            )}

            {scenariosLoading ? (
              <div className="glass-panel p-16 text-center">
                <div className="text-ork-cyan font-mono text-sm animate-pulse">Loading scenarios...</div>
              </div>
            ) : (
              <div className="glass-panel overflow-hidden">
                {scenarios.length === 0 ? (
                  <p className="text-ork-muted font-mono text-xs text-center py-12">
                    No scenarios yet. Create one to get started.
                  </p>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-ork-border">
                        <th className="data-label text-left px-4 py-2.5">Name</th>
                        <th className="data-label text-left px-4 py-2.5">Agent</th>
                        <th className="data-label text-left px-4 py-2.5">Assertions</th>
                        <th className="data-label text-left px-4 py-2.5">Timeout</th>
                        <th className="data-label text-left px-4 py-2.5">Tags</th>
                        <th className="data-label text-left px-4 py-2.5">Enabled</th>
                        <th className="data-label text-left px-4 py-2.5">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {scenarios.map((s) => (
                        <tr key={s.id} className="border-b border-ork-border/50 hover:bg-ork-hover/30 transition-colors">
                          <td className="px-4 py-2.5 font-mono text-ork-text font-medium">{s.name}</td>
                          <td className="px-4 py-2.5 font-mono text-ork-muted">{s.agent_id}</td>
                          <td className="px-4 py-2.5 font-mono text-ork-muted">{s.assertions?.length ?? 0}</td>
                          <td className="px-4 py-2.5 font-mono text-ork-dim">{s.timeout_seconds}s</td>
                          <td className="px-4 py-2.5">
                            <div className="flex gap-1 flex-wrap">
                              {s.tags?.map((tag) => (
                                <span key={tag} className="text-[10px] font-mono text-ork-purple bg-ork-purple/10 border border-ork-purple/20 px-1.5 py-0.5 rounded">
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="px-4 py-2.5">
                            <StatusBadge status={s.enabled ? "active" : "disabled"} />
                          </td>
                          <td className="px-4 py-2.5">
                            <div className="flex items-center gap-2">
                              <Link href={`/test-lab/scenarios/${s.id}`} className="flex items-center gap-1 text-ork-cyan hover:text-ork-cyan/80 transition-colors font-mono">
                                <Eye size={12} /> View
                              </Link>
                              <button
                                onClick={() => handleRun(s.id)}
                                disabled={runningId === s.id}
                                className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider bg-ork-green/15 text-ork-green border border-ork-green/30 rounded hover:bg-ork-green/25 transition-colors disabled:opacity-50"
                              >
                                <Play size={10} />
                                {runningId === s.id ? "Starting..." : "Run"}
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
