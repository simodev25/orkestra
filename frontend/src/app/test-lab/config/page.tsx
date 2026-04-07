"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { request } from "@/lib/api-client";
import {
  Settings, Save, Bot, Brain, Wrench, Clock, Shield, Target, FileText,
  ChevronDown, ChevronUp, RefreshCw, Check,
} from "lucide-react";

const AGENT_DEFS = [
  {
    key: "preparation",
    name: "ScenarioSubAgent",
    icon: FileText,
    color: "purple",
    description: "Generates and adapts test scenarios. Produces a structured test plan before the target agent is executed.",
  },
  {
    key: "assertion",
    name: "PolicySubAgent",
    icon: Target,
    color: "green",
    description: "Checks governance compliance: forbidden effects, scope boundaries, family rules. Verifies the agent respects its constraints.",
  },
  {
    key: "diagnostic",
    name: "RobustnessSubAgent",
    icon: Shield,
    color: "amber",
    description: "Proposes follow-up edge cases, adversarial inputs, and robustness tests based on previous run results.",
  },
  {
    key: "verdict",
    name: "JudgeSubAgent",
    icon: Brain,
    color: "cyan",
    description: "Evaluates the target agent output. Produces verdict (PASS/FAIL/PARTIAL), score (0-100), and rationale.",
  },
];

const COLOR_MAP: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  purple: { bg: "bg-ork-purple/5", border: "border-ork-purple/20", text: "text-ork-purple", dot: "bg-ork-purple" },
  green: { bg: "bg-ork-green/5", border: "border-ork-green/20", text: "text-ork-green", dot: "bg-ork-green" },
  amber: { bg: "bg-ork-amber/5", border: "border-ork-amber/20", text: "text-ork-amber", dot: "bg-ork-amber" },
  cyan: { bg: "bg-ork-cyan/5", border: "border-ork-cyan/20", text: "text-ork-cyan", dot: "bg-ork-cyan" },
};

export default function TestLabConfigPage() {
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<any[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [expandedAgent, setExpandedAgent] = useState<string | null>(null);
  const [availableSkills, setAvailableSkills] = useState<any[]>([]);

  useEffect(() => {
    request<any>("/api/test-lab/config")
      .then(setConfig)
      .catch((e: any) => setError(e.message || "Failed to load config"))
      .finally(() => setLoading(false));
  }, []);

  function loadModels(provider: string) {
    setLoadingModels(true);
    request<{ models: string[] }>(`/api/test-lab/config/models/${provider}`)
      .then((data) => setModels(data.models || []))
      .catch(() => {})
      .finally(() => setLoadingModels(false));
  }

  useEffect(() => {
    if (config?.orchestrator?.provider) {
      loadModels(config.orchestrator.provider);
    }
  }, [config?.orchestrator?.provider]);

  useEffect(() => {
    request<any>("/api/test-lab/config/skills")
      .then((data) => setAvailableSkills(Array.isArray(data) ? data : data.items ?? []))
      .catch(() => {});
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    try {
      const updated = await request<any>("/api/test-lab/config", {
        method: "PUT",
        body: JSON.stringify(config),
      });
      setConfig(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) { setError(e.message || "Failed to save"); }
    finally { setSaving(false); }
  }

  function updateWorker(key: string, field: string, value: any) {
    setConfig({
      ...config,
      workers: {
        ...config.workers,
        [key]: { ...config.workers?.[key], [field]: value },
      },
    });
  }

  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan animate-pulse">Loading...</div>
      </div>
    );
  }

  const modelOptions = models.map((m: any) => m.name);

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link href="/test-lab" className="text-xs font-mono text-ork-dim hover:text-ork-cyan">← Back to Test Lab</Link>
          <div className="flex items-center gap-3 mt-1">
            <Settings size={20} className="text-ork-cyan" />
            <h1 className="text-xl font-semibold">Test Lab Configuration</h1>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {saved && <span className="text-xs font-mono text-ork-green flex items-center gap-1"><Check size={12} /> Saved</span>}
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider rounded border bg-ork-cyan/10 text-ork-cyan border-ork-cyan/30 hover:bg-ork-cyan/20 transition-colors disabled:opacity-40">
            <Save size={13} /> {saving ? "Saving..." : "Save all"}
          </button>
        </div>
      </div>

      {error && <div className="glass-panel p-3 border-ork-red/30 bg-ork-red/5"><p className="text-xs font-mono text-ork-red">{error}</p></div>}

      {/* Global LLM */}
      <section className="glass-panel p-5 space-y-4">
        <h2 className="section-title flex items-center gap-2"><Brain size={13} /> OrchestratorAgent LLM</h2>
        <p className="text-[11px] text-ork-dim">Model used by the OrchestratorAgent and as default for SubAgents unless overridden.</p>
        <div className="grid grid-cols-[200px_1fr] gap-4">
          <div>
            <label className="data-label block mb-1.5">Provider</label>
            <select
              value={config?.orchestrator?.provider || "ollama"}
              onChange={(e) => {
                setConfig({ ...config, orchestrator: { ...config.orchestrator, provider: e.target.value } });
                loadModels(e.target.value);
              }}
              className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text focus:outline-none focus:border-ork-cyan/40">
              <option value="ollama">Ollama Cloud</option>
              <option value="openai">OpenAI / Mistral</option>
            </select>
          </div>
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="data-label">Model</label>
              <button onClick={() => loadModels(config?.orchestrator?.provider || "ollama")} disabled={loadingModels}
                className="text-[10px] font-mono text-ork-dim hover:text-ork-cyan flex items-center gap-1">
                <RefreshCw size={10} className={loadingModels ? "animate-spin" : ""} /> {loadingModels ? "Loading..." : "Refresh"}
              </button>
            </div>
            <ModelSelect
              value={config?.orchestrator?.model || ""}
              options={modelOptions}
              onChange={(v) => setConfig({ ...config, orchestrator: { ...config.orchestrator, model: v } })}
              placeholder="Select a model..."
            />
          </div>
        </div>
      </section>

      {/* Agent Cards */}
      <section className="space-y-3">
        <h2 className="section-title flex items-center gap-2"><Bot size={13} /> SubAgents (used by OrchestratorAgent during test runs)</h2>
        <p className="text-[11px] text-ork-dim mb-2">Each phase of the test is handled by a specialized agent. Click to expand and configure.</p>

        {AGENT_DEFS.map((agent) => {
          const Icon = agent.icon;
          const colors = COLOR_MAP[agent.color];
          const isExpanded = expandedAgent === agent.key;
          const workerConfig = config?.workers?.[agent.key] || {};
          const hasOverride = !!workerConfig.model;

          return (
            <div key={agent.key} className={`rounded-lg border transition-all ${isExpanded ? colors.border : "border-ork-border"} ${isExpanded ? colors.bg : "bg-ork-surface"}`}>
              {/* Card header */}
              <button
                onClick={() => setExpandedAgent(isExpanded ? null : agent.key)}
                className="w-full px-4 py-3 flex items-center gap-3 text-left"
              >
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${colors.bg} border ${colors.border}`}>
                  <Icon size={16} className={colors.text} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ork-text">{agent.name}</span>
                    {hasOverride && (
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-ork-amber/10 text-ork-amber border border-ork-amber/20">
                        custom model
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-ork-dim truncate">{agent.description}</p>
                </div>
                <div className={`text-ork-dim transition-transform ${isExpanded ? "rotate-180" : ""}`}>
                  <ChevronDown size={16} />
                </div>
              </button>

              {/* Expanded config */}
              {isExpanded && (
                <div className="px-4 pb-4 space-y-4 animate-fade-in border-t border-ork-border/50">
                  <div className="pt-3">
                    <label className="data-label block mb-1.5">System prompt</label>
                    <textarea
                      value={workerConfig.prompt || ""}
                      onChange={(e) => updateWorker(agent.key, "prompt", e.target.value)}
                      rows={5}
                      className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40 resize-y"
                    />
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1.5">
                      <label className="data-label">Model override</label>
                      <span className="text-[10px] text-ork-dim">(leave empty to use default LLM)</span>
                    </div>
                    <ModelSelect
                      value={workerConfig.model || ""}
                      options={modelOptions}
                      onChange={(v) => updateWorker(agent.key, "model", v || null)}
                      placeholder="Use default model"
                      allowEmpty
                    />
                  </div>

                  {/* Skills */}
                  <div>
                    <label className="data-label block mb-1.5">Skills</label>
                    <div className="space-y-2">
                      {/* Current skills */}
                      {(workerConfig.skills || []).length > 0 && (
                        <div className="flex gap-1.5 flex-wrap">
                          {(workerConfig.skills || []).map((sid: string) => {
                            const skill = availableSkills.find((s: any) => s.id === sid);
                            return (
                              <span key={sid} className="flex items-center gap-1 text-[10px] font-mono px-2 py-1 rounded bg-ork-purple/10 text-ork-purple border border-ork-purple/20">
                                {skill?.label || sid}
                                <button onClick={() => updateWorker(agent.key, "skills", (workerConfig.skills || []).filter((s: string) => s !== sid))}
                                  className="text-ork-red hover:text-ork-red/80 ml-1">&times;</button>
                              </span>
                            );
                          })}
                        </div>
                      )}
                      {/* Add skill */}
                      <select
                        value=""
                        onChange={(e) => {
                          if (!e.target.value) return;
                          const current = workerConfig.skills || [];
                          if (!current.includes(e.target.value)) {
                            updateWorker(agent.key, "skills", [...current, e.target.value]);
                          }
                        }}
                        className="w-full px-3 py-1.5 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text focus:outline-none focus:border-ork-cyan/40"
                      >
                        <option value="">+ Add a skill...</option>
                        {availableSkills
                          .filter((s: any) => !(workerConfig.skills || []).includes(s.id))
                          .map((s: any) => (
                            <option key={s.id} value={s.id}>[{s.category}] {s.label}</option>
                          ))
                        }
                      </select>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </section>

      {/* Default Settings */}
      <section className="glass-panel p-5 space-y-4">
        <h2 className="section-title flex items-center gap-2"><Clock size={13} /> Default Scenario Settings</h2>
        <div className="grid grid-cols-3 gap-4">
          {[
            { key: "timeout_seconds", label: "Timeout (s)", default: 120 },
            { key: "max_iterations", label: "Max iterations", default: 5 },
            { key: "retry_count", label: "Retry count", default: 0 },
          ].map((f) => (
            <div key={f.key}>
              <label className="data-label block mb-1.5">{f.label}</label>
              <input type="number"
                value={config?.defaults?.[f.key] ?? f.default}
                onChange={(e) => setConfig({ ...config, defaults: { ...config.defaults, [f.key]: parseInt(e.target.value) || 0 } })}
                className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text focus:outline-none focus:border-ork-cyan/40"
              />
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}


function ModelSelect({ value, options, onChange, placeholder, allowEmpty }: {
  value: string; options: string[]; onChange: (v: string) => void; placeholder: string; allowEmpty?: boolean;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = search ? options.filter((o) => o.toLowerCase().includes(search.toLowerCase())) : options;

  return (
    <div className="relative">
      <input
        type="text"
        value={open ? search : value || ""}
        onChange={(e) => { setSearch(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
      />
      {/* Backdrop must be BEFORE dropdown so dropdown buttons receive clicks */}
      {open && <div className="fixed inset-0 z-40" onClick={() => { setOpen(false); setSearch(""); }} />}
      {open && (
        <div className="absolute z-50 w-full mt-1 max-h-48 overflow-y-auto bg-ork-surface border border-ork-border rounded shadow-lg">
          {allowEmpty && (
            <button onClick={() => { onChange(""); setOpen(false); setSearch(""); }}
              className="w-full text-left px-3 py-1.5 text-xs font-mono text-ork-dim hover:bg-ork-hover">
              — None (use default) —
            </button>
          )}
          {filtered.length === 0 && <p className="px-3 py-2 text-xs text-ork-dim">No models found</p>}
          {filtered.map((m) => (
            <button key={m} onClick={() => { onChange(m); setOpen(false); setSearch(""); }}
              className={`w-full text-left px-3 py-1.5 text-xs font-mono hover:bg-ork-hover transition-colors ${
                m === value ? "text-ork-cyan bg-ork-cyan/5" : "text-ork-text"
              }`}>
              {m}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
