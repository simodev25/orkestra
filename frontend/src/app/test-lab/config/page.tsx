"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { Settings, Save, Bot, Brain, Wrench, Clock } from "lucide-react";

export default function TestLabConfigPage() {
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/test-lab/config")
      .then((r) => r.json())
      .then(setConfig)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const res = await fetch("/api/test-lab/config", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      });
      if (!res.ok) throw new Error("Failed to save");
      const updated = await res.json();
      setConfig(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan animate-pulse">Loading configuration...</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Settings size={20} className="text-ork-cyan" />
            <h1 className="text-xl font-semibold">Test Lab Configuration</h1>
          </div>
          <p className="text-xs text-ork-muted mt-1">Configure LLM models, worker prompts, and default settings for the Agentic Test Lab</p>
        </div>
        <div className="flex items-center gap-3">
          {saved && <span className="text-xs font-mono text-ork-green">Saved!</span>}
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider rounded border bg-ork-cyan/10 text-ork-cyan border-ork-cyan/30 hover:bg-ork-cyan/20 transition-colors disabled:opacity-40"
          >
            <Save size={13} /> {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-panel p-3 border-ork-red/30 bg-ork-red/5">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      {/* Orchestrator Model */}
      <section className="glass-panel p-5 space-y-4">
        <h2 className="section-title flex items-center gap-2"><Brain size={13} /> Orchestrator & Worker Model</h2>
        <p className="text-[11px] text-ork-dim">LLM model used for orchestrator decisions and worker agents (preparation, assertion, diagnostic, verdict)</p>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="data-label block mb-1.5">Provider</label>
            <select
              value={config?.orchestrator?.provider || "ollama"}
              onChange={(e) => setConfig({ ...config, orchestrator: { ...config.orchestrator, provider: e.target.value } })}
              className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text focus:outline-none focus:border-ork-cyan/40"
            >
              <option value="ollama">Ollama (cloud)</option>
              <option value="openai">OpenAI / Mistral</option>
            </select>
          </div>
          <div>
            <label className="data-label block mb-1.5">Model</label>
            <input
              type="text"
              value={config?.orchestrator?.model || ""}
              onChange={(e) => setConfig({ ...config, orchestrator: { ...config.orchestrator, model: e.target.value } })}
              placeholder="gpt-oss:20b-cloud"
              className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
            />
          </div>
        </div>
      </section>

      {/* Worker Prompts */}
      <section className="glass-panel p-5 space-y-4">
        <h2 className="section-title flex items-center gap-2"><Bot size={13} /> Worker Agent Prompts</h2>
        <p className="text-[11px] text-ork-dim">System prompts for each worker agent. These define how each phase analyzes the test results.</p>

        {["preparation", "assertion", "diagnostic", "verdict"].map((worker) => (
          <div key={worker} className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="data-label capitalize">{worker} worker</label>
              <span className="text-[10px] font-mono text-ork-dim">
                {(config?.workers?.[worker]?.model) ? `model: ${config.workers[worker].model}` : "uses default model"}
              </span>
            </div>
            <textarea
              value={config?.workers?.[worker]?.prompt || ""}
              onChange={(e) => setConfig({
                ...config,
                workers: {
                  ...config.workers,
                  [worker]: { ...config.workers?.[worker], prompt: e.target.value },
                },
              })}
              rows={3}
              className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40 resize-y"
            />
            <div>
              <label className="data-label block mb-1">Model override (optional)</label>
              <input
                type="text"
                value={config?.workers?.[worker]?.model || ""}
                onChange={(e) => setConfig({
                  ...config,
                  workers: {
                    ...config.workers,
                    [worker]: { ...config.workers?.[worker], model: e.target.value || null },
                  },
                })}
                placeholder="Leave empty to use orchestrator model"
                className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
              />
            </div>
          </div>
        ))}
      </section>

      {/* Default Scenario Settings */}
      <section className="glass-panel p-5 space-y-4">
        <h2 className="section-title flex items-center gap-2"><Clock size={13} /> Default Scenario Settings</h2>

        <div className="grid grid-cols-3 gap-4">
          <div>
            <label className="data-label block mb-1.5">Timeout (seconds)</label>
            <input
              type="number"
              value={config?.defaults?.timeout_seconds || 120}
              onChange={(e) => setConfig({ ...config, defaults: { ...config.defaults, timeout_seconds: parseInt(e.target.value) } })}
              className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text focus:outline-none focus:border-ork-cyan/40"
            />
          </div>
          <div>
            <label className="data-label block mb-1.5">Max iterations</label>
            <input
              type="number"
              value={config?.defaults?.max_iterations || 5}
              onChange={(e) => setConfig({ ...config, defaults: { ...config.defaults, max_iterations: parseInt(e.target.value) } })}
              className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text focus:outline-none focus:border-ork-cyan/40"
            />
          </div>
          <div>
            <label className="data-label block mb-1.5">Retry count</label>
            <input
              type="number"
              value={config?.defaults?.retry_count || 0}
              onChange={(e) => setConfig({ ...config, defaults: { ...config.defaults, retry_count: parseInt(e.target.value) } })}
              className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text focus:outline-none focus:border-ork-cyan/40"
            />
          </div>
        </div>
      </section>

      {/* Available Models Reference */}
      <section className="glass-panel p-5 space-y-3">
        <h2 className="section-title flex items-center gap-2"><Wrench size={13} /> Available Ollama Cloud Models</h2>
        <div className="flex gap-2 flex-wrap">
          {["gpt-oss:20b", "gpt-oss:120b", "deepseek-v3.1:671b", "gemma4:31b", "qwen3-next:80b",
            "nemotron-3-super", "minimax-m2.7", "devstral-small-2:24b", "ministral-3:8b"].map((m) => (
            <button
              key={m}
              onClick={() => setConfig({ ...config, orchestrator: { ...config.orchestrator, model: m } })}
              className="text-[10px] font-mono px-2 py-1 rounded border border-ork-border text-ork-muted hover:text-ork-cyan hover:border-ork-cyan/30 transition-colors"
            >
              {m}
            </button>
          ))}
        </div>
        <p className="text-[10px] text-ork-dim">Click a model to set it as the orchestrator model. Suffix &quot;-cloud&quot; is added automatically.</p>
      </section>
    </div>
  );
}
