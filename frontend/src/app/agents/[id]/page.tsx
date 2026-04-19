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
      <div className="p-6 max-w-5xl mx-auto">
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">Loading agent details...</div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="glass-panel p-6 text-sm font-mono text-ork-red">{error ?? "Agent not found"}</div>
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
    <div className="p-6 max-w-5xl mx-auto space-y-4 animate-fade-in">
      {/* ── Header ── */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href="/agents" className="text-xs font-mono text-ork-dim hover:text-ork-cyan">
            ← Back to Agent Registry
          </Link>
          <h1 className="text-xl font-semibold mt-2">{agent.name}</h1>
          <p className="text-xs font-mono text-ork-dim mt-1">
            {agent.id} · family={agent.family?.label || agent.family_id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={agent.status} />
          <Link
            href="/test-lab"
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10"
          >
            Test Lab
          </Link>
          <Link
            href={`/agents/${agent.id}/edit`}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-purple/30 text-ork-purple bg-ork-purple/10"
          >
            Edit
          </Link>
          <button
            onClick={() => setConfirmDeleteOpen(true)}
            disabled={deleting}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-red/30 text-ork-red bg-ork-red/10 disabled:opacity-50"
          >
            {deleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>

      {actionError && (
        <div className="glass-panel p-3 border border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{actionError}</p>
        </div>
      )}

      <AgentLifecyclePanel
        agent={agent}
        onStatusChange={(updated) => setAgent(updated)}
      />

      {/* ── Tabs ── */}
      <div className="flex gap-0 border-b border-ork-border">
        <button
          onClick={() => setTab("details")}
          className={`flex items-center gap-2 px-5 py-2.5 text-xs font-mono uppercase tracking-wider border-b-2 transition-colors ${
            tab === "details"
              ? "border-ork-purple text-ork-purple"
              : "border-transparent text-ork-dim hover:text-ork-muted"
          }`}
        >
          <FileText size={13} />
          Details
        </button>
        <button
          onClick={() => setTab("chat")}
          className={`flex items-center gap-2 px-5 py-2.5 text-xs font-mono uppercase tracking-wider border-b-2 transition-colors ${
            tab === "chat"
              ? "border-ork-cyan text-ork-cyan"
              : "border-transparent text-ork-dim hover:text-ork-muted"
          }`}
        >
          <MessageSquare size={13} />
          Chat direct
        </button>
      </div>

      {/* ── Tab: Chat direct ── */}
      {tab === "chat" && (
        <div className="glass-panel flex flex-col" style={{ height: "60vh" }}>
          {/* Chat header */}
          {chatMessages.length > 0 && (
            <div className="flex justify-end px-4 pt-2 flex-shrink-0">
              <button
                onClick={() => setChatMessages([])}
                className="text-[10px] font-mono text-ork-dim/50 hover:text-ork-red transition-colors"
              >
                Effacer l'historique
              </button>
            </div>
          )}
          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {chatMessages.length === 0 && (
              <div className="flex items-center justify-center h-full">
                <p className="text-xs font-mono text-ork-dim text-center">
                  Parle directement à <span className="text-ork-cyan">{agent.name}</span>.<br />
                  <span className="text-ork-dim/50">Pas de scénario, pas de scoring — conversation brute.</span>
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
          <div className="border-t border-ork-border/60 px-4 py-3 flex items-end gap-3 flex-shrink-0">
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
              className="flex-1 resize-none bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim/50 focus:outline-none focus:border-ork-cyan/40 transition-colors disabled:opacity-50 min-h-[38px] max-h-[100px] overflow-y-auto"
              style={{ height: "auto" }}
              onInput={(e) => {
                const el = e.currentTarget;
                el.style.height = "auto";
                el.style.height = `${Math.min(el.scrollHeight, 100)}px`;
              }}
            />
            <button
              onClick={() => void sendChat(chatInput)}
              disabled={chatLoading || !chatInput.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider bg-ork-cyan/15 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/25 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex-shrink-0"
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
        <KV label="name" value={agent.name} />
        <KV label="agent_id" value={agent.id} mono />
        <KV label="family_id" value={agent.family_id} mono />
        <KV label="family" value={agent.family ? `${agent.family.label} — ${agent.family.description || "no description"}` : "-"} />
        <KV label="version" value={agent.version} mono />
        <KV label="status" value={agent.status} mono />
        <KV label="owner" value={agent.owner || "-"} mono />
      </Section>

      <Section title="Mission / Description">
        <KV label="purpose" value={agent.purpose} />
        <KV label="description" value={agent.description || "-"} />
      </Section>

      <Section title="Skills">
        {agent.skills_resolved && agent.skills_resolved.length > 0 ? (
          <div className="space-y-1">
            {agent.skills_resolved.map((s) => (
              <div key={s.skill_id} className="text-xs font-mono flex gap-2">
                <span className="text-ork-cyan">{s.skill_id}</span>
                <span className="text-ork-text">{s.label}</span>
                <span className="text-ork-dim">[{s.category}]</span>
              </div>
            ))}
          </div>
        ) : (
          <KV label="skill_ids" value={skillIds.length > 0 ? skillIds.join(", ") : "-"} />
        )}
      </Section>

      <Section title="Selection hints">
        <pre className="text-xs font-mono text-ork-muted whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3">
{JSON.stringify(agent.selection_hints ?? {}, null, 2)}
        </pre>
      </Section>

      {isOrchestrator ? (
        /* Pipeline section replaces MCP permissions for orchestrators */
        <Section title="Pipeline d'agents">
          <div className="mb-2 flex items-center gap-2">
            <span className="text-[10px] text-ork-dim uppercase tracking-widest">Mode de routage</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
              (agent.routing_mode ?? "sequential") === "dynamic"
                ? "border-purple-500/40 text-purple-400 bg-purple-500/10"
                : "border-ork-cyan/40 text-ork-cyan bg-ork-cyan/10"
            }`}>
              {(agent.routing_mode ?? "sequential") === "dynamic" ? "Dynamique (LLM choisit)" : "Séquentiel (ordre fixe)"}
            </span>
          </div>
          {(agent.pipeline_agent_ids ?? []).length === 0 ? (
            <p className="text-sm text-ork-dim font-mono">Aucun agent configuré dans ce pipeline.</p>
          ) : (
            <div className="flex flex-col gap-2">
              {(agent.pipeline_agent_ids ?? []).map((agentId, idx) => (
                <div key={agentId} className="flex items-center gap-3 bg-ork-bg border border-ork-border rounded-md px-3 py-2">
                  <span className="bg-ork-cyan text-black text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0">
                    {idx + 1}
                  </span>
                  <span className="text-xs text-ork-cyan font-mono flex-1">{agentId}</span>
                  <a
                    href={`/agents/${agentId}`}
                    className="text-[10px] text-ork-dim hover:text-ork-cyan transition-colors"
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
            <p className="text-sm text-ork-dim font-mono">No allowed MCPs configured.</p>
          ) : (
            <div className="space-y-2">
              {allowedMcps.map((mcpId) => {
                const mcp = mcpMap.get(mcpId);
                return (
                  <div key={mcpId} className="border border-ork-border rounded p-2 text-xs font-mono">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-ork-cyan">{mcpId}</span>
                      {mcp ? (
                        <>
                          <span className="text-ork-text">{mcp.name}</span>
                          <span className="text-ork-dim">{mcp.effect_type}</span>
                          <StatusBadge status={mcp.orkestra_state} />
                          <StatusBadge status={mcp.obot_state} />
                        </>
                      ) : (
                        <span className="text-ork-dim">not present in current catalog snapshot</span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <KV label="forbidden_effects" value={forbiddenEffects.length > 0 ? forbiddenEffects.join(", ") : "-"} />
        </Section>
      )}

      <Section title="Contracts">
        <KV label="input_contract_ref" value={agent.input_contract_ref || "-"} mono />
        <KV label="output_contract_ref" value={agent.output_contract_ref || "-"} mono />
      </Section>

      <Section title="Prompt">
        <KV label="prompt_ref" value={agent.prompt_ref || "-"} mono />
        <pre className="text-xs font-mono text-ork-text whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3">
{agent.prompt_content || "-"}
        </pre>
      </Section>

      <Section title="Skills file">
        <KV label="skills_ref" value={agent.skills_ref || "-"} mono />
        <pre className="text-xs font-mono text-ork-text whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3">
{agent.skills_content || "-"}
        </pre>
      </Section>

      <Section title="Limitations">
        <KV label="limitations" value={limitations.length > 0 ? limitations.join(", ") : "-"} />
      </Section>

      <Section title="Reliability / Tests">
        <KV label="last_test_status" value={agent.last_test_status || "not_tested"} mono />
        <KV label="last_validated_at" value={agent.last_validated_at || "-"} mono />
      </Section>

      <Section title="Usage metadata">
        <KV label="usage_count" value={String(agent.usage_count)} mono />
        <KV label="criticality" value={agent.criticality} />
        <KV label="cost_profile" value={agent.cost_profile} />
        <KV label="created_at" value={agent.created_at} mono />
        <KV label="updated_at" value={agent.updated_at} mono />
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
    <section className="glass-panel p-4 space-y-2">
      <h2 className="section-title text-sm">{title}</h2>
      {children}
    </section>
  );
}

function KV({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[180px_1fr] gap-3 items-start text-xs">
      <p className="data-label">{label}</p>
      <p className={`${mono ? "font-mono" : ""} text-ork-text`}>{value}</p>
    </div>
  );
}
