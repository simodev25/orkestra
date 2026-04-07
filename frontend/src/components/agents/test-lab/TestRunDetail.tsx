"use client";

import { X, Bot, Brain, Wrench, Shield, FileText, Clock, Cpu } from "lucide-react";
import { StatusBadge } from "@/components/ui/status-badge";

interface TestRunDetailProps {
  run: any;
  onClose: () => void;
}

export function TestRunDetail({ run, onClose }: TestRunDetailProps) {
  const meta = run.metadata || {};
  const systemPrompt = meta.system_prompt || "";
  const tools = meta.tools || [];
  const mcps = meta.allowed_mcps || [];
  const skills = meta.skills || [];
  const forbidden = meta.forbidden_effects || [];
  const limitations = meta.limitations || [];

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-8 bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-4xl max-h-[85vh] overflow-y-auto bg-ork-surface border border-ork-border rounded-lg shadow-2xl animate-fade-in">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-ork-surface border-b border-ork-border px-5 py-4 flex items-start justify-between">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <FileText size={16} className="text-ork-cyan" />
              Test Run Detail
            </h2>
            <p className="text-xs font-mono text-ork-dim mt-1">
              {run.id} · {new Date(run.timestamp || run.created_at).toLocaleString()}
            </p>
          </div>
          <button onClick={onClose} className="p-1 rounded hover:bg-ork-hover text-ork-muted hover:text-ork-text">
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {/* Summary bar */}
          <div className="flex items-center gap-4 flex-wrap text-xs font-mono">
            <StatusBadge status={run.verdict || run.status} />
            <span className="flex items-center gap-1 text-ork-muted"><Clock size={12} /> {run.latencyMs || run.latency_ms}ms</span>
            {meta.llm_provider && <span className="text-ork-muted">{meta.llm_provider}/{meta.llm_model}</span>}
            <span className="text-ork-muted">v{run.agentVersion || run.agent_version}</span>
            {meta.criticality && <StatusBadge status={meta.criticality} />}
          </div>

          {/* Agent info */}
          <Section title="Agent" icon={<Bot size={14} />}>
            <KV label="Name" value={meta.agent_name || run.agentId || run.agent_id} />
            <KV label="Family" value={meta.family_id || "-"} />
            <KV label="Purpose" value={meta.purpose || "-"} />
            {meta.prompt_ref && <KV label="Prompt ref" value={meta.prompt_ref} mono />}
          </Section>

          {/* User task */}
          <Section title="Task / instruction" icon={<FileText size={14} />}>
            <pre className="text-xs font-mono text-ork-text whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3">
              {run.task || run.rawOutput ? (run.task || "") : "No task recorded"}
            </pre>
          </Section>

          {/* System prompt */}
          {systemPrompt && (
            <Section title="System prompt (multi-layer)" icon={<Brain size={14} />}>
              <pre className="text-xs font-mono text-ork-muted whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3 max-h-64 overflow-y-auto">
                {systemPrompt}
              </pre>
            </Section>
          )}

          {/* Skills */}
          {skills.length > 0 && (
            <Section title={`Skills (${skills.length})`} icon={<Bot size={14} />}>
              <div className="space-y-1">
                {skills.map((s: any) => (
                  <div key={s.skill_id} className="flex gap-2 text-xs font-mono">
                    <span className="text-ork-cyan">{s.skill_id}</span>
                    <span className="text-ork-text">{s.label}</span>
                    <span className="text-ork-dim">[{s.category}]</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Tools & MCP */}
          <Section title="Tools / MCP" icon={<Wrench size={14} />}>
            <KV label="Allowed MCPs" value={mcps.length > 0 ? mcps.join(", ") : "none"} />
            <KV label="Registered tools" value={tools.length > 0 ? tools.join(", ") : "none"} />
            <KV label="Forbidden effects" value={forbidden.length > 0 ? forbidden.join(", ") : "none"} />
          </Section>

          {/* Limitations */}
          {limitations.length > 0 && (
            <Section title="Limitations" icon={<Shield size={14} />}>
              <ul className="text-xs text-ork-muted space-y-0.5">
                {limitations.map((l: string, i: number) => (
                  <li key={i} className="font-mono">- {l}</li>
                ))}
              </ul>
            </Section>
          )}

          {/* LLM Response */}
          <Section title="LLM response" icon={<Cpu size={14} />}>
            <pre className="text-xs font-mono text-ork-text whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3 max-h-80 overflow-y-auto">
              {run.rawOutput || run.raw_output || "No output"}
            </pre>
          </Section>

          {/* Behavioral checks */}
          {run.behavioralChecks && run.behavioralChecks.length > 0 && (
            <Section title={`Behavioral checks (${run.behavioralChecks.length})`} icon={<Shield size={14} />}>
              <div className="space-y-1">
                {run.behavioralChecks.map((c: any) => (
                  <div key={c.key} className={`flex items-center gap-2 text-xs font-mono ${c.actual === "pass" ? "text-ork-green" : "text-ork-red"}`}>
                    <span>{c.actual === "pass" ? "PASS" : "FAIL"}</span>
                    <span className="text-ork-text">{c.label}</span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Error */}
          {(run.notes || run.error_message) && (
            <Section title="Error" icon={<X size={14} />}>
              <p className="text-xs font-mono text-ork-red">{run.notes || run.error_message}</p>
            </Section>
          )}
        </div>
      </div>
    </div>
  );
}

function Section({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="glass-panel p-4 space-y-2">
      <h3 className="section-title text-xs flex items-center gap-1.5">{icon} {title}</h3>
      {children}
    </div>
  );
}

function KV({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[140px_1fr] gap-2 text-xs">
      <span className="data-label">{label}</span>
      <span className={`${mono ? "font-mono" : ""} text-ork-text`}>{value}</span>
    </div>
  );
}
