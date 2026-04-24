"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useParams, useRouter } from "next/navigation";
import { Loader2, MessageSquare, Send, FileText } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";
import { AgentLifecyclePanel } from "@/components/agents/lifecycle/AgentLifecyclePanel";
import { deleteAgent, getAgent, listMcpCatalogForAgentDesign } from "@/lib/agent-registry/service";
import { request } from "@/lib/api-client";
import type { AgentDefinition, McpCatalogSummary } from "@/lib/agent-registry/types";

// ─── Chat types ───────────────────────────────────────────────────────────────

interface ToolCall {
  tool_name?: string;
  name?: string;
  tool_input?: string;
  tool_output?: string;
}

interface ChatMessage {
  role: "user" | "agent" | "error";
  content: string;
  raw_output?: string;
  tool_calls?: ToolCall[];
  duration_ms?: number;
}

interface ChatResponse {
  response: string;
  raw_output?: string;
  tool_calls: ToolCall[];
  duration_ms: number;
  status: string;
}

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [agent, setAgent] = useState<AgentDefinition | null>(null);
  const [catalogMcps, setCatalogMcps] = useState<McpCatalogSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);

  // ─── Tab & Chat state ─────────────────────────────────────────────────────
  const [tab, setTab] = useState<"details" | "chat">("details");
  const storageKey = `chat_${id}`;
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(() => {
    try {
      const saved = localStorage.getItem(storageKey);
      return saved ? (JSON.parse(saved) as ChatMessage[]) : [];
    } catch {
      return [];
    }
  });
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const chatInputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify(chatMessages)); } catch { /* quota */ }
  }, [chatMessages, storageKey]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, chatLoading]);

  const sendChat = useCallback(async (text: string) => {
    if (!text.trim() || chatLoading || !agent) return;
    setChatInput("");
    setChatMessages((prev) => [...prev, { role: "user", content: text.trim() }]);
    setChatLoading(true);
    try {
      const resp = await request<ChatResponse>(`/api/agents/${agent.id}/chat`, {
        method: "POST",
        body: JSON.stringify({ message: text.trim() }),
      });
      setChatMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: resp.response || "(no response)",
          raw_output: resp.raw_output,
          tool_calls: resp.tool_calls ?? [],
          duration_ms: resp.duration_ms,
        },
      ]);
    } catch (e: unknown) {
      setChatMessages((prev) => [
        ...prev,
        { role: "error", content: e instanceof Error ? e.message : "Request failed" },
      ]);
    } finally {
      setChatLoading(false);
      setTimeout(() => chatInputRef.current?.focus(), 50);
    }
  }, [agent, chatLoading]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getAgent(id), listMcpCatalogForAgentDesign()])
      .then(([agentValue, mcpCatalog]) => {
        if (cancelled) return;
        setAgent(agentValue);
        setCatalogMcps(mcpCatalog);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load agent");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const mcpMap = useMemo(() => {
    const map = new Map<string, McpCatalogSummary>();
    for (const mcp of catalogMcps) map.set(mcp.id, mcp);
    return map;
  }, [catalogMcps]);

  if (loading) {
    return (
      <div className="page animate-fade-in">
        <div className="glass-panel" style={{ padding: "64px", textAlign: "center", fontFamily: "var(--font-mono)", fontSize: "13px", color: "var(--ork-cyan)" }}>Loading agent details...</div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="page animate-fade-in">
        <div className="glass-panel" style={{ padding: "20px", fontFamily: "var(--font-mono)", fontSize: "13px", color: "var(--ork-red)" }}>{error ?? "Agent not found"}</div>
      </div>
    );
  }

  const isOrchestrator = agent.family_id === "orchestration";
  const skillIds = agent.skill_ids ?? [];
  const allowedMcps = agent.allowed_mcps ?? [];
  const forbiddenEffects = agent.forbidden_effects ?? [];
  const limitations = agent.limitations ?? [];

  async function confirmDelete(agentId: string) {
    setDeleting(true);
    setActionError(null);
    try {
      await deleteAgent(agentId);
      router.push("/agents");
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : "Failed to delete agent");
      setDeleting(false);
      setConfirmDeleteOpen(false);
    }
  }

  return (
    <div className="page animate-fade-in">
      {/* ── Header ── */}
      <div className="pagehead">
        <div>
          <Link href="/agents" className="section-title" style={{ color: "var(--ork-muted)", marginBottom: "6px", display: "inline-block" }}>
            ← Back to Agent Registry
          </Link>
          <h1>{agent.name}</h1>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
            {agent.id} · family={agent.family?.label || agent.family_id}
          </p>
        </div>
        <div className="pagehead__actions">
          <StatusBadge status={agent.status} />
          <Link
            href="/test-lab"
            className="btn"
          >
            Test Lab
          </Link>
          <Link
            href={`/agents/${agent.id}/edit`}
            className="btn btn--purple"
          >
            Edit
          </Link>
          <button
            onClick={() => setConfirmDeleteOpen(true)}
            disabled={deleting}
            className="btn btn--red"
            style={{ opacity: deleting ? 0.5 : 1 }}
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>

      {actionError && (
        <div className="glass-panel" style={{ padding: "10px 14px", border: "1px solid color-mix(in oklch, var(--ork-red) 30%, transparent)", marginBottom: "8px" }}>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-red)", margin: 0 }}>{actionError}</p>
        </div>
      )}

      <AgentLifecyclePanel
        agent={agent}
        onStatusChange={(updated) => setAgent(updated)}
      />

      {/* ── Tabs ── */}
      <div className="tabs" style={{ marginTop: "8px" }}>
        <button
          onClick={() => setTab("details")}
          className={`tabs__btn${tab === "details" ? " tabs__btn--active" : ""}`}
        >
          <FileText size={13} />
          Details
        </button>
        <button
          onClick={() => setTab("chat")}
          className={`tabs__btn${tab === "chat" ? " tabs__btn--active" : ""}`}
        >
          <MessageSquare size={13} />
          Chat direct
        </button>
      </div>

      {/* ── Tab: Chat direct ── */}
      {tab === "chat" && (
        <div className="glass-panel" style={{ display: "flex", flexDirection: "column", height: "60vh", marginTop: "8px" }}>
          {/* Chat header */}
          {chatMessages.length > 0 && (
            <div style={{ display: "flex", justifyContent: "flex-end", padding: "8px 16px 0", flexShrink: 0 }}>
              <button
                onClick={() => setChatMessages([])}
                className="btn"
                style={{ fontSize: "10px", color: "var(--ork-muted-2)" }}
              >
                Effacer l&apos;historique
              </button>
            </div>
          )}
          {/* Messages */}
          <div style={{ flex: 1, overflowY: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "10px" }}>
            {chatMessages.length === 0 && (
              <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%" }}>
                <p style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-muted-2)", textAlign: "center" }}>
                  Parle directement à <span style={{ color: "var(--ork-cyan)" }}>{agent.name}</span>.<br />
                  <span style={{ color: "var(--ork-muted-2)", opacity: 0.6 }}>Pas de scénario, pas de scoring — conversation brute.</span>
                </p>
              </div>
            )}
            {chatMessages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                {msg.role === "user" && (
                  <div className="max-w-[75%] bg-ork-cyan/10 border border-ork-cyan/30 rounded-lg rounded-tr-sm px-4 py-2.5">
                    <p className="text-[10px] font-mono text-ork-cyan/60 mb-1 uppercase tracking-wider">you</p>
                    <p className="text-sm text-ork-text">{msg.content}</p>
                  </div>
                )}
                {msg.role === "agent" && (
                  <div className="max-w-[80%] bg-ork-surface border border-ork-dim/20 rounded-lg rounded-tl-sm px-4 py-2.5">
                    <div className="flex items-center gap-2 mb-1.5">
                      <p className="text-[10px] font-mono text-ork-purple/70 uppercase tracking-wider">{agent.name}</p>
                      {msg.duration_ms && (
                        <span className="text-[10px] font-mono text-ork-dim/50">{msg.duration_ms}ms</span>
                      )}
                    </div>
                    <AgentMessageContent content={msg.content} />
                    {msg.raw_output && msg.raw_output !== msg.content && (
                      <details className="mt-2">
                        <summary className="text-[10px] font-mono text-ork-dim/50 cursor-pointer hover:text-ork-dim select-none">
                          Résultat brut JSON ▸
                        </summary>
                        <ToolOutputContent output={msg.raw_output} />
                      </details>
                    )}
                    {msg.tool_calls && msg.tool_calls.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-ork-border/30 space-y-1">
                        {msg.tool_calls.map((tc, j) => {
                          const toolName = tc.tool_name ?? tc.name ?? "tool";
                          const hasOutput = !!tc.tool_output;
                          return hasOutput ? (
                            <details key={j} className="group">
                              <summary className="flex items-center gap-1.5 cursor-pointer list-none">
                                <span className="text-[10px] font-mono text-ork-amber bg-ork-amber/10 border border-ork-amber/20 px-2 py-0.5 rounded">
                                  {toolName} ▸
                                </span>
                              </summary>
                              <ToolOutputContent output={tc.tool_output!} />
                            </details>
                          ) : (
                            <span key={j} className="inline-block text-[10px] font-mono text-ork-amber bg-ork-amber/10 border border-ork-amber/20 px-2 py-0.5 rounded">
                              {toolName}
                            </span>
                          );
                        })}
                      </div>
                    )}
                  </div>
                )}
                {msg.role === "error" && (
                  <div className="max-w-[80%] bg-ork-red/5 border border-ork-red/30 rounded-lg px-4 py-2.5">
                    <p className="text-xs font-mono text-ork-red">{msg.content}</p>
                  </div>
                )}
              </div>
            ))}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-ork-surface border border-ork-dim/20 rounded-lg rounded-tl-sm px-4 py-3 flex items-center gap-2">
                  <Loader2 size={13} className="text-ork-cyan animate-spin" />
                  <span className="text-xs font-mono text-ork-dim animate-pulse">
                    {agent.name} is thinking…
                  </span>
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Input */}
          <div style={{ borderTop: "1px solid var(--ork-border)", padding: "10px 16px", display: "flex", alignItems: "flex-end", gap: "10px", flexShrink: 0 }}>
            <textarea
              ref={chatInputRef}
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void sendChat(chatInput);
                }
              }}
              placeholder={`Message ${agent.name}… (Enter to send)`}
              disabled={chatLoading}
              rows={1}
              className="field"
              style={{ flex: 1, resize: "none", height: "auto", minHeight: "36px", maxHeight: "100px", overflowY: "auto", padding: "8px 10px", opacity: chatLoading ? 0.5 : 1 }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 100)}px`;
              }}
            />
            <button
              onClick={() => void sendChat(chatInput)}
              disabled={chatLoading || !chatInput.trim()}
              className="btn btn--cyan"
              style={{ opacity: chatLoading || !chatInput.trim() ? 0.4 : 1, cursor: chatLoading || !chatInput.trim() ? "not-allowed" : undefined, flexShrink: 0 }}
            >
              {chatLoading ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
              Send
            </button>
          </div>
        </div>
      )}

      {/* ── Tab: Details ── */}
      {tab === "details" && (<>

      <Section title="Identity">
        <div className="kv">
          <span className="k">name</span><span className="v">{agent.name}</span>
          <span className="k">agent_id</span><span className="v mono">{agent.id}</span>
          <span className="k">family_id</span><span className="v mono">{agent.family_id}</span>
          <span className="k">family</span><span className="v">{agent.family ? `${agent.family.label} — ${agent.family.description || "no description"}` : "-"}</span>
          <span className="k">version</span><span className="v mono">{agent.version}</span>
          <span className="k">status</span><span className="v mono">{agent.status}</span>
          <span className="k">owner</span><span className="v mono">{agent.owner || "-"}</span>
        </div>
      </Section>

      <Section title="Mission / Description">
        <div className="kv">
          <span className="k">purpose</span><span className="v">{agent.purpose}</span>
          <span className="k">description</span><span className="v">{agent.description || "-"}</span>
        </div>
      </Section>

      <Section title="Skills">
        {agent.skills_resolved && agent.skills_resolved.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
            {agent.skills_resolved.map((s) => (
              <div key={s.skill_id} style={{ fontFamily: "var(--font-mono)", fontSize: "12px", display: "flex", gap: "8px" }}>
                <span style={{ color: "var(--ork-cyan)" }}>{s.skill_id}</span>
                <span style={{ color: "var(--ork-text)" }}>{s.label}</span>
                <span style={{ color: "var(--ork-muted-2)" }}>[{s.category}]</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="kv">
            <span className="k">skill_ids</span>
            <span className="v mono">{skillIds.length > 0 ? skillIds.join(", ") : "-"}</span>
          </div>
        )}
      </Section>

      <Section title="Selection hints">
        <pre style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-muted)", whiteSpace: "pre-wrap", background: "var(--ork-bg)", border: "1px solid var(--ork-border)", borderRadius: "var(--radius)", padding: "10px 12px", margin: 0 }}>
{JSON.stringify(agent.selection_hints ?? {}, null, 2)}
        </pre>
      </Section>

      {isOrchestrator ? (
        /* Pipeline section replaces MCP permissions for orchestrators */
        <Section title="Pipeline d'agents">
          <div style={{ marginBottom: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--ork-muted-2)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Mode de routage</span>
            <span className={`chip${
              (agent.routing_mode ?? "sequential") === "dynamic"
                ? ""
                : ""
            }`} style={{
              color: (agent.routing_mode ?? "sequential") === "dynamic" ? "var(--ork-purple)" : "var(--ork-cyan)",
              background: (agent.routing_mode ?? "sequential") === "dynamic" ? "var(--ork-purple-bg)" : "var(--ork-cyan-bg)",
              borderColor: (agent.routing_mode ?? "sequential") === "dynamic"
                ? "color-mix(in oklch, var(--ork-purple) 40%, transparent)"
                : "color-mix(in oklch, var(--ork-cyan) 40%, transparent)",
            }}>
              {(agent.routing_mode ?? "sequential") === "dynamic" ? "Dynamique (LLM choisit)" : "Séquentiel (ordre fixe)"}
            </span>
          </div>
          {(agent.pipeline_agent_ids ?? []).length === 0 ? (
            <p style={{ fontFamily: "var(--font-mono)", fontSize: "13px", color: "var(--ork-muted-2)" }}>Aucun agent configuré dans ce pipeline.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {(agent.pipeline_agent_ids ?? []).map((agentId, idx) => (
                <div key={agentId} style={{ display: "flex", alignItems: "center", gap: "10px", background: "var(--ork-bg)", border: "1px solid var(--ork-border)", borderRadius: "var(--radius)", padding: "6px 10px" }}>
                  <span style={{ background: "var(--ork-cyan)", color: "oklch(0.15 0.03 145)", fontFamily: "var(--font-mono)", fontSize: "10px", fontWeight: 700, padding: "1px 6px", borderRadius: "var(--radius)", flexShrink: 0 }}>
                    {idx + 1}
                  </span>
                  <span style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-cyan)", flex: 1 }}>{agentId}</span>
                  <a
                    href={`/agents/${agentId}`}
                    style={{ fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--ork-muted-2)" }}
                  >
                    voir →
                  </a>
                </div>
              ))}
            </div>
          )}
        </Section>
      ) : (
        /* Normal MCP permissions section for non-orchestrators */
        <Section title="MCP permissions">
          {allowedMcps.length === 0 ? (
            <p style={{ fontFamily: "var(--font-mono)", fontSize: "13px", color: "var(--ork-muted-2)" }}>No allowed MCPs configured.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              {allowedMcps.map((mcpId) => {
                const mcp = mcpMap.get(mcpId);
                return (
                  <div key={mcpId} style={{ border: "1px solid var(--ork-border)", borderRadius: "var(--radius)", padding: "6px 10px", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "8px" }}>
                      <span style={{ color: "var(--ork-cyan)" }}>{mcpId}</span>
                      {mcp ? (
                        <>
                          <span style={{ color: "var(--ork-text)" }}>{mcp.name}</span>
                          <span style={{ color: "var(--ork-muted-2)" }}>{mcp.effect_type}</span>
                          <StatusBadge status={mcp.orkestra_state} />
                          <StatusBadge status={mcp.obot_state} />
                        </>
                      ) : (
                        <span style={{ color: "var(--ork-muted-2)" }}>not present in current catalog snapshot</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <div className="kv" style={{ marginTop: "8px" }}>
            <span className="k">forbidden_effects</span>
            <span className="v">{forbiddenEffects.length > 0 ? forbiddenEffects.join(", ") : "-"}</span>
          </div>
        </Section>
      )}

      <Section title="Contracts">
        <div className="kv">
          <span className="k">input_contract_ref</span><span className="v mono">{agent.input_contract_ref || "-"}</span>
          <span className="k">output_contract_ref</span><span className="v mono">{agent.output_contract_ref || "-"}</span>
        </div>
      </Section>

      <Section title="Prompt">
        <div className="kv" style={{ marginBottom: "8px" }}>
          <span className="k">prompt_ref</span><span className="v mono">{agent.prompt_ref || "-"}</span>
        </div>
        <pre style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-text)", whiteSpace: "pre-wrap", background: "var(--ork-bg)", border: "1px solid var(--ork-border)", borderRadius: "var(--radius)", padding: "10px 12px", margin: 0 }}>
{agent.prompt_content || "-"}
        </pre>
      </Section>

      <Section title="Skills file">
        <div className="kv" style={{ marginBottom: "8px" }}>
          <span className="k">skills_ref</span><span className="v mono">{agent.skills_ref || "-"}</span>
        </div>
        <pre style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-text)", whiteSpace: "pre-wrap", background: "var(--ork-bg)", border: "1px solid var(--ork-border)", borderRadius: "var(--radius)", padding: "10px 12px", margin: 0 }}>
{agent.skills_content || "-"}
        </pre>
      </Section>

      <Section title="Limitations">
        <div className="kv">
          <span className="k">limitations</span>
          <span className="v">{limitations.length > 0 ? limitations.join(", ") : "-"}</span>
        </div>
      </Section>

      <Section title="Reliability / Tests">
        <div className="kv">
          <span className="k">last_test_status</span><span className="v mono">{agent.last_test_status || "not_tested"}</span>
          <span className="k">last_validated_at</span><span className="v mono">{agent.last_validated_at || "-"}</span>
        </div>
      </Section>

      <Section title="Usage metadata">
        <div className="kv">
          <span className="k">usage_count</span><span className="v mono">{String(agent.usage_count)}</span>
          <span className="k">criticality</span><span className="v">{agent.criticality}</span>
          <span className="k">cost_profile</span><span className="v">{agent.cost_profile}</span>
          <span className="k">created_at</span><span className="v mono">{agent.created_at}</span>
          <span className="k">updated_at</span><span className="v mono">{agent.updated_at}</span>
        </div>
      </Section>

      <ConfirmDangerDialog
        open={confirmDeleteOpen}
        title="Delete Agent"
        description="This removes the agent definition from Orkestra Registry. This action cannot be undone."
        targetLabel={`${agent.name} (${agent.id})`}
        confirmLabel="Delete Agent"
        loading={deleting}
        onCancel={() => {
          if (deleting) return;
          setConfirmDeleteOpen(false);
        }}
        onConfirm={() => void confirmDelete(agent.id)}
      />
      </> )}

    </div>
  );
}

function ToolOutputContent({ output }: { output: string }) {
  const trimmed = output.trim();
  try {
    const parsed = JSON.parse(trimmed);
    return (
      <pre className="mt-1 text-[10px] font-mono text-ork-muted/70 whitespace-pre-wrap bg-ork-bg rounded p-2 border border-ork-amber/20 overflow-x-auto max-h-48 overflow-y-auto">
        {JSON.stringify(parsed, null, 2)}
      </pre>
    );
  } catch {
    return (
      <pre className="mt-1 text-[10px] font-mono text-ork-muted/70 whitespace-pre-wrap bg-ork-bg rounded p-2 border border-ork-amber/20 max-h-48 overflow-y-auto">
        {output}
      </pre>
    );
  }
}

function AgentMessageContent({ content }: { content: string }) {
  // Try to parse as JSON for pretty display
  const trimmed = content.trim();
  if ((trimmed.startsWith("{") || trimmed.startsWith("[")) ) {
    try {
      const parsed = JSON.parse(trimmed);
      return (
        <div className="space-y-2">
          {/* Key fields summary for objects */}
          {typeof parsed === "object" && !Array.isArray(parsed) && (
            <div className="space-y-1">
              {Object.entries(parsed as Record<string, unknown>).map(([k, v]) => {
                if (typeof v === "object" && v !== null) return null;
                const val = String(v);
                const isGood = k === "resolved" && v === true;
                const isBad = k === "resolved" && v === false;
                return (
                  <div key={k} className="grid grid-cols-[140px_1fr] gap-2 text-xs font-mono">
                    <span className="text-ork-dim">{k}</span>
                    <span className={isGood ? "text-ork-cyan" : isBad ? "text-ork-red" : "text-ork-text"}>{val}</span>
                  </div>
                );
              })}
            </div>
          )}
          {/* Full JSON collapsible */}
          <details className="mt-1">
            <summary className="text-[10px] font-mono text-ork-dim/60 cursor-pointer hover:text-ork-dim select-none">
              JSON complet
            </summary>
            <pre className="mt-1 text-[10px] font-mono text-ork-muted/70 whitespace-pre-wrap bg-ork-bg rounded p-2 border border-ork-border/30 overflow-x-auto max-h-48 overflow-y-auto">
              {JSON.stringify(parsed, null, 2)}
            </pre>
          </details>
        </div>
      );
    } catch {
      /* not valid JSON — fall through */
    }
  }
  return <p className="text-sm text-ork-muted whitespace-pre-wrap leading-relaxed">{content}</p>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="glass-panel" style={{ padding: "14px 16px", marginTop: "8px" }}>
      <h2 className="section-title" style={{ marginBottom: "10px" }}>{title}</h2>
      {children}
    </section>
  );
}
