"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import type { PolicyProfile, BudgetProfile, PlatformSecret } from "@/lib/types";

export default function AdminPage() {
  const [policies, setPolicies] = useState<PolicyProfile[]>([]);
  const [budgets, setBudgets] = useState<BudgetProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Policy form
  const [policyName, setPolicyName] = useState("");
  const [policyIsDefault, setPolicyIsDefault] = useState(false);
  const [policyHighCrit, setPolicyHighCrit] = useState(false);
  const [creatingPolicy, setCreatingPolicy] = useState(false);

  // Budget form
  const [budgetName, setBudgetName] = useState("");
  const [budgetSoftLimit, setBudgetSoftLimit] = useState("");
  const [budgetHardLimit, setBudgetHardLimit] = useState("");
  const [budgetIsDefault, setBudgetIsDefault] = useState(false);
  const [creatingBudget, setCreatingBudget] = useState(false);

  // Platform capabilities
  const [capabilities, setCapabilities] = useState<Record<string, boolean>>({});
  const [savingCap, setSavingCap] = useState<string | null>(null);

  // Secrets
  const [secrets, setSecrets] = useState<PlatformSecret[]>([]);
  const [openaiKey, setOpenaiKey] = useState("");
  const [ollamaKey, setOllamaKey] = useState("");
  const [savingSecret, setSavingSecret] = useState(false);
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<Record<string, { ok: boolean; message: string } | null>>({});

  const loadAll = useCallback(async () => {
    try {
      const [p, b, s, caps] = await Promise.all([
        api.listPolicies(),
        api.listBudgets(),
        api.listSecrets(),
        api.listCapabilities(),
      ]);
      setPolicies(p);
      setBudgets(b);
      setSecrets(s);
      setCapabilities(caps);
    } catch (err: any) {
      setError(err.message || "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  async function handleCreatePolicy() {
    if (!policyName.trim()) return;
    setCreatingPolicy(true);
    try {
      const rules: Record<string, boolean> = {};
      if (policyHighCrit) rules.high_criticality_requires_review = true;
      await api.createPolicy({
        name: policyName.trim(),
        is_default: policyIsDefault,
        rules,
      });
      setPolicyName("");
      setPolicyIsDefault(false);
      setPolicyHighCrit(false);
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create policy");
    } finally {
      setCreatingPolicy(false);
    }
  }

  async function handleCreateBudget() {
    if (!budgetName.trim()) return;
    setCreatingBudget(true);
    try {
      await api.createBudget({
        name: budgetName.trim(),
        soft_limit: budgetSoftLimit ? parseFloat(budgetSoftLimit) : null,
        hard_limit: budgetHardLimit ? parseFloat(budgetHardLimit) : null,
        is_default: budgetIsDefault,
      });
      setBudgetName("");
      setBudgetSoftLimit("");
      setBudgetHardLimit("");
      setBudgetIsDefault(false);
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to create budget");
    } finally {
      setCreatingBudget(false);
    }
  }

  async function handleSaveSecret(id: string, value: string, description: string) {
    setSavingSecret(true);
    try {
      await api.upsertSecret(id, value, description);
      setOpenaiKey("");
      setOllamaKey("");
      await loadAll();
    } catch (err: any) {
      setError(err.message || "Failed to save secret");
    } finally {
      setSavingSecret(false);
    }
  }

  async function handleTestKey(provider: "openai" | "ollama") {
    setTestingKey(provider);
    setTestResult((prev) => ({ ...prev, [provider]: null }));
    try {
      if (provider === "openai") {
        const key = openaiKey.trim() || secrets.find(s => s.id === "OPENAI_API_KEY")?.value;
        if (!key) {
          setTestResult((prev) => ({ ...prev, openai: { ok: false, message: "No API key configured or entered" } }));
          return;
        }
        const res = await fetch("https://api.openai.com/v1/models", {
          headers: { Authorization: `Bearer ${key}` },
        });
        if (res.ok) {
          const data = await res.json();
          const count = data.data?.length ?? 0;
          setTestResult((prev) => ({ ...prev, openai: { ok: true, message: `Connected — ${count} models available` } }));
        } else {
          const body = await res.json().catch(() => ({}));
          setTestResult((prev) => ({ ...prev, openai: { ok: false, message: body.error?.message || `HTTP ${res.status}` } }));
        }
      } else {
        // Test Ollama by listing models
        const ollamaHost = "http://localhost:11434";
        const res = await fetch(`${ollamaHost}/api/tags`).catch(() => null);
        if (res && res.ok) {
          const data = await res.json();
          const count = data.models?.length ?? 0;
          setTestResult((prev) => ({ ...prev, ollama: { ok: true, message: `Connected — ${count} models loaded` } }));
        } else {
          setTestResult((prev) => ({ ...prev, ollama: { ok: false, message: "Cannot reach Ollama at localhost:11434. Is it running?" } }));
        }
      }
    } catch (err: any) {
      setTestResult((prev) => ({ ...prev, [provider]: { ok: false, message: err.message || "Connection failed" } }));
    } finally {
      setTestingKey(null);
    }
  }

  async function handleToggleCapability(key: string, newValue: boolean) {
    setSavingCap(key);
    try {
      const updated = await api.setCapability(key, newValue);
      setCapabilities((prev) => ({ ...prev, [key]: updated.value }));
    } catch (err: any) {
      setError(err.message || "Failed to update capability");
    } finally {
      setSavingCap(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin mx-auto" />
          <p className="data-label">LOADING ADMINISTRATION...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title text-sm mb-1">ADMINISTRATION</h1>
          <p className="text-ork-dim text-xs font-mono">
            Policy profiles and budget configuration for governance enforcement
          </p>
        </div>
        {error && (
          <span className="text-[10px] font-mono text-ork-red bg-ork-red/10 border border-ork-red/20 rounded px-2 py-1">
            {error}
          </span>
        )}
      </div>

      {/* Security — API Keys */}
      <div className="glass-panel p-5 mb-6">
        <h2 className="section-title mb-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-ork-red" />
          SECURITY &mdash; API KEYS
        </h2>
        <p className="text-xs text-ork-dim font-mono mb-4">
          Configure LLM provider API keys. Keys are stored securely in the database.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* OpenAI */}
          <div className="bg-ork-bg rounded-lg p-4 border border-ork-border/50">
            <div className="flex items-center justify-between mb-2">
              <p className="data-label">OPENAI_API_KEY</p>
              {secrets.find(s => s.id === "OPENAI_API_KEY") ? (
                <span className="text-[9px] font-mono text-ork-green bg-ork-green/10 border border-ork-green/20 rounded px-1.5 py-0.5">CONFIGURED</span>
              ) : (
                <span className="text-[9px] font-mono text-ork-dim bg-ork-dim/10 border border-ork-dim/20 rounded px-1.5 py-0.5">NOT SET</span>
              )}
            </div>
            <input
              type="password"
              value={openaiKey}
              onChange={(e) => setOpenaiKey(e.target.value)}
              placeholder="sk-..."
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono mb-2 text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleSaveSecret("OPENAI_API_KEY", openaiKey, "OpenAI API key")}
                disabled={!openaiKey.trim() || savingSecret}
                className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 hover:bg-ork-cyan/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {savingSecret ? "Saving..." : "Save Key"}
              </button>
              <button
                onClick={() => handleTestKey("openai")}
                disabled={testingKey === "openai"}
                className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider rounded border border-ork-amber/30 text-ork-amber bg-ork-amber/10 hover:bg-ork-amber/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {testingKey === "openai" ? "Testing..." : "Test"}
              </button>
            </div>
            {testResult.openai && (
              <p className={`mt-2 text-[10px] font-mono ${testResult.openai.ok ? "text-ork-green" : "text-ork-red"}`}>
                {testResult.openai.ok ? "\u2713" : "\u2717"} {testResult.openai.message}
              </p>
            )}
          </div>
          {/* Ollama */}
          <div className="bg-ork-bg rounded-lg p-4 border border-ork-border/50">
            <div className="flex items-center justify-between mb-2">
              <p className="data-label">OLLAMA_API_KEY</p>
              {secrets.find(s => s.id === "OLLAMA_API_KEY") ? (
                <span className="text-[9px] font-mono text-ork-green bg-ork-green/10 border border-ork-green/20 rounded px-1.5 py-0.5">CONFIGURED</span>
              ) : (
                <span className="text-[9px] font-mono text-ork-dim bg-ork-dim/10 border border-ork-dim/20 rounded px-1.5 py-0.5">NOT SET</span>
              )}
            </div>
            <input
              type="password"
              value={ollamaKey}
              onChange={(e) => setOllamaKey(e.target.value)}
              placeholder="ollama-..."
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono mb-2 text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleSaveSecret("OLLAMA_API_KEY", ollamaKey, "Ollama API key")}
                disabled={!ollamaKey.trim() || savingSecret}
                className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 hover:bg-ork-cyan/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {savingSecret ? "Saving..." : "Save Key"}
              </button>
              <button
                onClick={() => handleTestKey("ollama")}
                disabled={testingKey === "ollama"}
                className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider rounded border border-ork-amber/30 text-ork-amber bg-ork-amber/10 hover:bg-ork-amber/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {testingKey === "ollama" ? "Testing..." : "Test"}
              </button>
            </div>
            {testResult.ollama && (
              <p className={`mt-2 text-[10px] font-mono ${testResult.ollama.ok ? "text-ork-green" : "text-ork-red"}`}>
                {testResult.ollama.ok ? "\u2713" : "\u2717"} {testResult.ollama.message}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Platform Capabilities */}
      <div className="glass-panel p-5 mb-6">
        <h2 className="section-title mb-1 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-ork-amber" />
          PLATFORM CAPABILITIES
        </h2>
        <p className="text-xs text-ork-dim font-mono mb-4">
          Global feature toggles. When disabled, the feature is unavailable even if enabled per-agent.
        </p>
        <div className="space-y-3">
          {/* Code Execution */}
          <div className="bg-ork-bg rounded-lg p-4 border border-ork-border/50 flex items-start justify-between gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1">
                <p className="data-label">CODE EXECUTION</p>
                <span
                  className={`text-[9px] font-mono px-1.5 py-0.5 rounded border ${
                    capabilities.code_execution_enabled
                      ? "bg-ork-amber/10 text-ork-amber border-ork-amber/20"
                      : "bg-ork-dim/10 text-ork-dim border-ork-dim/20"
                  }`}
                >
                  {capabilities.code_execution_enabled ? "ENABLED" : "DISABLED"}
                </span>
              </div>
              <p className="text-[11px] text-ork-muted font-mono leading-relaxed">
                Allows agents with <span className="text-ork-cyan">allow_code_execution</span> to run
                Python code via <span className="text-ork-cyan">execute_python_code</span>.
                Uses BaseSandbox (Docker isolation) when available, bare subprocess otherwise.
              </p>
              {capabilities.code_execution_enabled && (
                <p className="text-[10px] text-ork-amber font-mono mt-1">
                  Warning: ensure Docker socket is mounted in the API container for sandbox isolation.
                </p>
              )}
            </div>
            <button
              onClick={() => handleToggleCapability("code_execution_enabled", !capabilities.code_execution_enabled)}
              disabled={savingCap === "code_execution_enabled"}
              className={`shrink-0 px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider rounded border transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
                capabilities.code_execution_enabled
                  ? "border-ork-red/30 text-ork-red bg-ork-red/10 hover:bg-ork-red/20"
                  : "border-ork-green/30 text-ork-green bg-ork-green/10 hover:bg-ork-green/20"
              }`}
            >
              {savingCap === "code_execution_enabled"
                ? "Saving..."
                : capabilities.code_execution_enabled
                ? "Disable"
                : "Enable"}
            </button>
          </div>
        </div>
      </div>

      {/* Two column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Policy Profiles */}
        <div className="space-y-4">
          <div className="glass-panel p-5">
            <h2 className="section-title mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-ork-amber" />
              POLICY PROFILES
            </h2>

            {/* Existing policies */}
            {policies.length === 0 ? (
              <div className="text-center py-6">
                <p className="text-ork-muted text-sm">No policy profiles defined</p>
              </div>
            ) : (
              <div className="space-y-2 mb-4">
                {policies.map((p) => (
                  <div
                    key={p.id}
                    className="bg-ork-bg rounded-lg p-3 border border-ork-border/50 hover:border-ork-border transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-ork-text font-medium">{p.name}</span>
                        {p.is_default && (
                          <span className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wider bg-ork-cyan/10 text-ork-cyan border border-ork-cyan/20 rounded">
                            DEFAULT
                          </span>
                        )}
                      </div>
                      <span className="font-mono text-[10px] text-ork-dim">
                        {p.id.slice(0, 8)}
                      </span>
                    </div>
                    {p.description && (
                      <p className="text-xs text-ork-muted mb-2">{p.description}</p>
                    )}
                    <div className="flex flex-wrap gap-1">
                      {p.rules && typeof p.rules === "object" ? (
                        Object.entries(p.rules).map(([key, val]) => (
                          <span
                            key={key}
                            className={`inline-flex items-center px-1.5 py-0.5 text-[9px] font-mono rounded border ${
                              val
                                ? "bg-ork-green/10 text-ork-green border-ork-green/20"
                                : "bg-ork-dim/20 text-ork-muted border-ork-dim/30"
                            }`}
                          >
                            {key.replace(/_/g, " ")}
                            {val ? " \u2713" : " \u2717"}
                          </span>
                        ))
                      ) : (
                        <span className="text-[10px] font-mono text-ork-dim">No rules defined</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Create Policy Form */}
          <div className="glass-panel p-5">
            <h3 className="section-title mb-4">CREATE POLICY PROFILE</h3>
            <div className="space-y-3">
              <div>
                <label className="data-label block mb-1.5">NAME *</label>
                <input
                  type="text"
                  value={policyName}
                  onChange={(e) => setPolicyName(e.target.value)}
                  placeholder="e.g. strict-governance"
                  className="w-full bg-ork-bg border border-ork-border rounded-lg px-3 py-2 text-sm text-ork-text font-mono placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
                />
              </div>

              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 cursor-pointer group">
                  <div
                    className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                      policyIsDefault
                        ? "bg-ork-cyan/20 border-ork-cyan/40"
                        : "border-ork-border group-hover:border-ork-dim"
                    }`}
                    onClick={() => setPolicyIsDefault(!policyIsDefault)}
                  >
                    {policyIsDefault && (
                      <span className="text-ork-cyan text-[10px]">{"\u2713"}</span>
                    )}
                  </div>
                  <span className="text-xs text-ork-muted">Set as default</span>
                </label>
              </div>

              <div className="border-t border-ork-border/50 pt-3">
                <p className="data-label mb-2">RULES</p>
                <label className="flex items-center gap-2 cursor-pointer group">
                  <div
                    className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                      policyHighCrit
                        ? "bg-ork-amber/20 border-ork-amber/40"
                        : "border-ork-border group-hover:border-ork-dim"
                    }`}
                    onClick={() => setPolicyHighCrit(!policyHighCrit)}
                  >
                    {policyHighCrit && (
                      <span className="text-ork-amber text-[10px]">{"\u2713"}</span>
                    )}
                  </div>
                  <span className="text-xs text-ork-muted">
                    High criticality requires review
                  </span>
                </label>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  onClick={handleCreatePolicy}
                  disabled={creatingPolicy || !policyName.trim()}
                  className="px-4 py-2 text-[11px] font-mono uppercase tracking-wider rounded-lg border border-ork-green/30 bg-ork-green/10 text-ork-green hover:bg-ork-green/20 transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {creatingPolicy ? "CREATING..." : "CREATE POLICY"}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Budget Profiles */}
        <div className="space-y-4">
          <div className="glass-panel p-5">
            <h2 className="section-title mb-4 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-ork-green" />
              BUDGET PROFILES
            </h2>

            {/* Existing budgets */}
            {budgets.length === 0 ? (
              <div className="text-center py-6">
                <p className="text-ork-muted text-sm">No budget profiles defined</p>
              </div>
            ) : (
              <div className="space-y-2 mb-4">
                {budgets.map((b) => (
                  <div
                    key={b.id}
                    className="bg-ork-bg rounded-lg p-3 border border-ork-border/50 hover:border-ork-border transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-ork-text font-medium">{b.name}</span>
                        {b.is_default && (
                          <span className="inline-flex items-center px-1.5 py-0.5 text-[9px] font-mono uppercase tracking-wider bg-ork-cyan/10 text-ork-cyan border border-ork-cyan/20 rounded">
                            DEFAULT
                          </span>
                        )}
                      </div>
                      <span className="font-mono text-[10px] text-ork-dim">
                        {b.id.slice(0, 8)}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-3 mt-2">
                      <div>
                        <p className="data-label mb-0.5">SOFT LIMIT</p>
                        <p className="font-mono text-xs text-ork-amber">
                          {b.soft_limit != null ? `$${b.soft_limit.toFixed(2)}` : "\u2014"}
                        </p>
                      </div>
                      <div>
                        <p className="data-label mb-0.5">HARD LIMIT</p>
                        <p className="font-mono text-xs text-ork-red">
                          {b.hard_limit != null ? `$${b.hard_limit.toFixed(2)}` : "\u2014"}
                        </p>
                      </div>
                      <div>
                        <p className="data-label mb-0.5">MAX RUN COST</p>
                        <p className="font-mono text-xs text-ork-text">
                          {b.max_run_cost != null ? `$${b.max_run_cost.toFixed(2)}` : "\u2014"}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Create Budget Form */}
          <div className="glass-panel p-5">
            <h3 className="section-title mb-4">CREATE BUDGET PROFILE</h3>
            <div className="space-y-3">
              <div>
                <label className="data-label block mb-1.5">NAME *</label>
                <input
                  type="text"
                  value={budgetName}
                  onChange={(e) => setBudgetName(e.target.value)}
                  placeholder="e.g. standard-budget"
                  className="w-full bg-ork-bg border border-ork-border rounded-lg px-3 py-2 text-sm text-ork-text font-mono placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="data-label block mb-1.5">SOFT LIMIT ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={budgetSoftLimit}
                    onChange={(e) => setBudgetSoftLimit(e.target.value)}
                    placeholder="10.00"
                    className="w-full bg-ork-bg border border-ork-border rounded-lg px-3 py-2 text-sm text-ork-text font-mono placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
                  />
                </div>
                <div>
                  <label className="data-label block mb-1.5">HARD LIMIT ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    value={budgetHardLimit}
                    onChange={(e) => setBudgetHardLimit(e.target.value)}
                    placeholder="50.00"
                    className="w-full bg-ork-bg border border-ork-border rounded-lg px-3 py-2 text-sm text-ork-text font-mono placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
                  />
                </div>
              </div>
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 cursor-pointer group">
                  <div
                    className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                      budgetIsDefault
                        ? "bg-ork-cyan/20 border-ork-cyan/40"
                        : "border-ork-border group-hover:border-ork-dim"
                    }`}
                    onClick={() => setBudgetIsDefault(!budgetIsDefault)}
                  >
                    {budgetIsDefault && (
                      <span className="text-ork-cyan text-[10px]">{"\u2713"}</span>
                    )}
                  </div>
                  <span className="text-xs text-ork-muted">Set as default</span>
                </label>
              </div>
              <div className="flex justify-end pt-2">
                <button
                  onClick={handleCreateBudget}
                  disabled={creatingBudget || !budgetName.trim()}
                  className="px-4 py-2 text-[11px] font-mono uppercase tracking-wider rounded-lg border border-ork-green/30 bg-ork-green/10 text-ork-green hover:bg-ork-green/20 transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  {creatingBudget ? "CREATING..." : "CREATE BUDGET"}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
