"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import { FlaskConical, Settings, Plus, Send, ChevronDown, Loader2 } from "lucide-react";
import { request } from "@/lib/api-client";
import { listAgents } from "@/lib/agent-registry/service";
import type { AgentDefinition } from "@/lib/agent-registry/types";

// ─── Types ──────────────────────────────────────────────────────────────────

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

// ─── Constants ───────────────────────────────────────────────────────────────

const FOLLOWUP_LABELS: Record<string, string> = {
  stricter: "Plus strict",
  robustness: "Edge case",
  policy: "Test policy",
  rerun: "Rejouer",
  targeted: "Test ciblé",
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

// ─── Helpers ─────────────────────────────────────────────────────────────────

/** Render minimal markdown-like content: **bold** */
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
    error: "text-ork-red border-ork-red/30 bg-ork-red/10",
  };
  const cls = colorMap[verdict.toLowerCase()] ?? "text-ork-dim border-ork-border bg-ork-surface";
  return (
    <span className={`text-[10px] font-mono uppercase tracking-wider px-2 py-0.5 rounded border ${cls}`}>
      {verdict}
    </span>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function TestLabChatPage() {
  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const [status, setStatus] = useState<"idle" | "running" | "awaiting_user" | "completed">("idle");
  const [targetAgent, setTargetAgent] = useState<{ id: string; label: string } | null>(null);
  const [availableFollowups, setAvailableFollowups] = useState<string[]>([]);
  const [lastVerdict, setLastVerdict] = useState<string | null>(null);
  const [lastScore, setLastScore] = useState<number | null>(null);

  // UI state
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [selectedAgentId, setSelectedAgentId] = useState<string>("");
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [initError, setInitError] = useState<string | null>(null);

  const chatBottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // ── Auto-scroll ────────────────────────────────────────────────────────────
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation, status]);

  // ── Close dropdown on outside click ───────────────────────────────────────
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // ── Apply session response ─────────────────────────────────────────────────
  const applySession = useCallback((sess: SessionState) => {
    setConversation(sess.conversation ?? []);
    setStatus(sess.current_status);
    setAvailableFollowups(sess.available_followups ?? []);
    setLastVerdict(sess.last_verdict);
    setLastScore(sess.last_score);
    if (sess.target_agent_id) {
      setTargetAgent({ id: sess.target_agent_id, label: sess.target_agent_label ?? sess.target_agent_id });
    }
  }, []);

  // ── Init: load agents + create session ────────────────────────────────────
  useEffect(() => {
    async function init() {
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
        setInitError(msg);
        setConversation([{ role: "system", content: `Error: ${msg}` }]);
      }
    }
    void init();
  }, [applySession]);

  // ── Send message ───────────────────────────────────────────────────────────
  const sendMessage = useCallback(async (text: string) => {
    if (!sessionId || !text.trim() || loading) return;
    setLoading(true);
    setInput("");

    // Optimistic: add user message immediately
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
      setStatus("awaiting_user");
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [sessionId, loading, applySession]);

  // ── Handle agent selection ─────────────────────────────────────────────────
  const handleSelectAgent = useCallback(async (agent: AgentDefinition) => {
    setSelectedAgentId(agent.id);
    setDropdownOpen(false);
    await sendMessage(`use ${agent.id}`);
  }, [sendMessage]);

  // ── Handle follow-up click ─────────────────────────────────────────────────
  const handleFollowup = useCallback((key: string) => {
    const msg = FOLLOWUP_MESSAGES[key] ?? key;
    void sendMessage(msg);
  }, [sendMessage]);

  // ── New session ────────────────────────────────────────────────────────────
  const handleNewSession = useCallback(async () => {
    setLoading(true);
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
      const msg = e instanceof Error ? e.message : "Failed to create session";
      setConversation([{ role: "system", content: `Error: ${msg}` }]);
    } finally {
      setLoading(false);
    }
  }, [applySession]);

  // ── Submit on Enter (no shift) ─────────────────────────────────────────────
  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void sendMessage(input);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────
  // Render
  // ─────────────────────────────────────────────────────────────────────────

  const selectedAgent = agents.find((a) => a.id === selectedAgentId);

  return (
    <div className="flex flex-col h-screen bg-ork-bg">
      {/* ── Top bar ── */}
      <div className="flex-shrink-0 border-b border-ork-border/60 bg-ork-surface/50 backdrop-blur px-5 py-3">
        <div className="max-w-[900px] mx-auto flex items-center gap-3 flex-wrap">
          {/* Title */}
          <div className="flex items-center gap-2 flex-1 min-w-0">
            <FlaskConical size={15} className="text-ork-purple flex-shrink-0" />
            <span className="font-mono text-xs tracking-widest text-ork-text uppercase truncate">
              Orkestra Test Lab — Interactive Session
            </span>
          </div>

          {/* Agent dropdown */}
          <div className="relative" ref={dropdownRef}>
            <button
              onClick={() => setDropdownOpen((v) => !v)}
              disabled={loading}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-surface border border-ork-border rounded hover:border-ork-dim transition-colors disabled:opacity-50 min-w-[160px]"
            >
              <span className="flex-1 text-left truncate text-ork-muted">
                {selectedAgent ? selectedAgent.name : "Select Agent"}
              </span>
              <ChevronDown size={11} className={`text-ork-dim transition-transform ${dropdownOpen ? "rotate-180" : ""}`} />
            </button>
            {dropdownOpen && (
              <div className="absolute top-full left-0 mt-1 z-50 glass-panel min-w-[220px] max-h-64 overflow-y-auto shadow-xl">
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
            disabled={loading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-surface text-ork-muted border border-ork-border rounded hover:text-ork-text hover:border-ork-dim transition-colors disabled:opacity-50"
          >
            <Plus size={11} />
            New Session
          </button>

          {/* Config link */}
          <Link
            href="/test-lab/config"
            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-surface text-ork-muted border border-ork-border rounded hover:text-ork-text hover:border-ork-dim transition-colors"
          >
            <Settings size={11} />
            Config
          </Link>
        </div>
      </div>

      {/* ── Status bar ── */}
      {(targetAgent || lastVerdict || status !== "idle") && (
        <div className="flex-shrink-0 border-b border-ork-border/30 bg-ork-bg/80 px-5 py-2">
          <div className="max-w-[900px] mx-auto flex items-center gap-4 text-[10px] font-mono text-ork-dim flex-wrap">
            {targetAgent && (
              <span>
                Agent: <span className="text-ork-cyan">{targetAgent.label}</span>
                <span className="text-ork-dim/60 ml-1">({targetAgent.id})</span>
              </span>
            )}
            <span>
              Status:{" "}
              <span
                className={
                  status === "running"
                    ? "text-ork-amber"
                    : status === "completed"
                    ? "text-ork-green"
                    : status === "awaiting_user"
                    ? "text-ork-cyan"
                    : "text-ork-dim"
                }
              >
                {status}
              </span>
            </span>
            {lastVerdict && <VerdictBadge verdict={lastVerdict} />}
            {lastScore !== null && (
              <span>
                Score:{" "}
                <span
                  className={
                    lastScore >= 80 ? "text-ork-green" : lastScore >= 50 ? "text-ork-amber" : "text-ork-red"
                  }
                >
                  {lastScore}/100
                </span>
              </span>
            )}
            {sessionId && (
              <span className="ml-auto text-ork-dim/40 truncate max-w-[200px]" title={sessionId}>
                {sessionId}
              </span>
            )}
          </div>
        </div>
      )}

      {/* ── Chat messages ── */}
      <div className="flex-1 overflow-y-auto px-5 py-4">
        <div className="max-w-[900px] mx-auto space-y-4">
          {initError && conversation.length === 0 && (
            <p className="text-center text-xs font-mono text-ork-red italic">{initError}</p>
          )}

          {conversation.map((msg, idx) => {
            const isLastOrchestratorMsg =
              msg.role === "orchestrator" &&
              idx === conversation.map((m) => m.role).lastIndexOf("orchestrator");

            return (
              <div key={idx}>
                {/* System message: centered */}
                {msg.role === "system" && (
                  <div className="flex justify-center">
                    <div className="max-w-[80%] text-center">
                      <p className="text-ork-dim italic text-xs font-mono px-4 py-1.5">
                        {msg.content}
                      </p>
                    </div>
                  </div>
                )}

                {/* User message: right-aligned */}
                {msg.role === "user" && (
                  <div className="flex justify-end">
                    <div className="max-w-[75%] bg-ork-cyan/10 border border-ork-cyan/30 rounded-lg rounded-tr-sm px-4 py-2.5">
                      <p className="text-[10px] font-mono text-ork-cyan/60 mb-1 uppercase tracking-wider">
                        user
                      </p>
                      <p className="text-sm text-ork-text leading-relaxed">{msg.content}</p>
                    </div>
                  </div>
                )}

                {/* Orchestrator message: left-aligned */}
                {msg.role === "orchestrator" && (
                  <div className="flex justify-start">
                    <div className="max-w-[80%] bg-ork-surface border border-ork-dim/20 rounded-lg rounded-tl-sm px-4 py-2.5">
                      <p className="text-[10px] font-mono text-ork-purple/70 mb-1.5 uppercase tracking-wider">
                        orchestrator
                      </p>
                      <div className="text-sm text-ork-muted leading-relaxed whitespace-pre-wrap">
                        {renderContent(msg.content)}
                      </div>

                      {/* Follow-up buttons on last orchestrator message */}
                      {isLastOrchestratorMsg && availableFollowups.length > 0 && !loading && (
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

          {/* Running indicator */}
          {status === "running" && (
            <div className="flex justify-start">
              <div className="bg-ork-surface border border-ork-dim/20 rounded-lg rounded-tl-sm px-4 py-3 flex items-center gap-2">
                <Loader2 size={13} className="text-ork-cyan animate-spin" />
                <span className="text-xs font-mono text-ork-dim animate-pulse">
                  Running test…
                </span>
              </div>
            </div>
          )}

          {/* Loading (send in progress) */}
          {loading && status !== "running" && (
            <div className="flex justify-start">
              <div className="bg-ork-surface border border-ork-dim/20 rounded-lg rounded-tl-sm px-4 py-3 flex items-center gap-2">
                <Loader2 size={13} className="text-ork-dim animate-spin" />
                <span className="text-xs font-mono text-ork-dim">Processing…</span>
              </div>
            </div>
          )}

          <div ref={chatBottomRef} />
        </div>
      </div>

      {/* ── Input bar ── */}
      <div className="flex-shrink-0 border-t border-ork-border/60 bg-ork-surface/50 backdrop-blur px-5 py-3">
        <div className="max-w-[900px] mx-auto flex items-end gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              !sessionId
                ? "Initializing session…"
                : !targetAgent
                ? "Select an agent above, or type a message to start…"
                : "Type your message… (Enter to send, Shift+Enter for newline)"
            }
            disabled={loading || !sessionId}
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
            onClick={() => void sendMessage(input)}
            disabled={loading || !input.trim() || !sessionId}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-cyan/15 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
          >
            {loading ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
            Send
          </button>
        </div>
        <p className="max-w-[900px] mx-auto mt-1.5 text-[10px] font-mono text-ork-dim/40">
          Enter to send · Shift+Enter for newline · Click follow-up buttons for suggested next steps
        </p>
      </div>
    </div>
  );
}
