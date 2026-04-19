"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { request } from "@/lib/api-client";
import type { PolicyProfile, BudgetProfile, PlatformSecret, LlmConfig } from "@/lib/types";

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

  // LLM Config
  const [llmConfig, setLlmConfig] = useState<LlmConfig>({
    provider: "ollama",
    ollama_host: "http://localhost:11434",
    ollama_model: "mistral",
    openai_model: "mistral-small-latest",
    openai_base_url: "https://api.mistral.ai/v1",
  });
  const [savingLlm, setSavingLlm] = useState(false);
  const [llmSaved, setLlmSaved] = useState(false);
  const [llmModels, setLlmModels] = useState<string[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmApiKeySet, setLlmApiKeySet] = useState(false);

  function loadModels(provider: string) {
    setLoadingModels(true);
    request<{ models: any[] }>(`/api/agents/llm-models/${provider}`)
      .then((data) => setLlmModels((data.models || []).map((m: any) => typeof m === "string" ? m : m.name)))
      .catch(() => {})
      .finally(() => setLoadingModels(false));
  }

  // Secrets
  const [secrets, setSecrets] = useState<PlatformSecret[]>([]);

  const loadAll = useCallback(async () => {
    try {
      const [p, b, s, caps, llm] = await Promise.all([
        api.listPolicies(),
        api.listBudgets(),
        api.listSecrets(),
        api.listCapabilities(),
        api.getLlmConfig(),
      ]);
      setPolicies(p);
      setBudgets(b);
      setSecrets(s);
      setCapabilities(caps);
      setLlmConfig(llm);
      loadModels(llm.provider || "ollama");
      // Check if LLM api key is already saved
      const secretId = (llm.provider === "openai" || llm.provider === "mistral") ? "OPENAI_API_KEY" : "OLLAMA_API_KEY";
      setLlmApiKeySet(s.some((sec: any) => sec.id === secretId));
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

  async function handleSaveLlmConfig() {
    setSavingLlm(true);
    setLlmSaved(false);
    try {
      await api.saveLlmConfig(llmConfig);
      // Also save the API key if provided
      if (llmApiKey.trim()) {
        const secretId = (llmConfig.provider === "openai" || llmConfig.provider === "mistral")
          ? "OPENAI_API_KEY"
          : "OLLAMA_API_KEY";
        await api.upsertSecret(secretId, llmApiKey.trim(), `${llmConfig.provider} API key`);
        setLlmApiKey("");
        setLlmApiKeySet(true);
      }
      setLlmSaved(true);
      setTimeout(() => setLlmSaved(false), 3000);
    } catch (err: any) {
      setError(err.message || "Failed to save LLM config");
    } finally {
      setSavingLlm(false);
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

      {/* LLM Configuration */}
      <div className="glass-panel p-5 mb-6">
        <h2 className="section-title mb-4 flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-ork-cyan" />
          LLM CONFIGURATION
        </h2>
        <p className="text-xs text-ork-dim font-mono mb-4">
          Provider and model used by the Orchestrator Builder. Overrides environment variables.
        </p>

        {/* Provider toggle */}
        <div className="mb-4">
          <label className="data-label block mb-2">PROVIDER</label>
          <div className="flex bg-[#0d1117] border border-[#2d3748] rounded-full p-0.5 w-fit">
            {(["ollama", "openai", "mistral"] as const).map((p) => (
              <button
                key={p}
                onClick={() => {
                  setLlmConfig((c) => ({ ...c, provider: p }));
                  loadModels(p);
                  const sid = (p === "openai" || p === "mistral") ? "OPENAI_API_KEY" : "OLLAMA_API_KEY";
                  setLlmApiKeySet(secrets.some((s) => s.id === sid));
                  setLlmApiKey("");
                }}
                className={`text-xs px-4 py-1.5 rounded-full transition-colors font-mono ${
                  llmConfig.provider === p
                    ? "bg-ork-cyan text-black font-bold"
                    : "text-ork-dim hover:text-ork-text"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          {llmConfig.provider === "ollama" ? (
            <>
              <div>
                <label className="data-label block mb-1.5">OLLAMA HOST</label>
                <input
                  type="text"
                  value={llmConfig.ollama_host}
                  onChange={(e) => setLlmConfig((c) => ({ ...c, ollama_host: e.target.value }))}
                  placeholder="http://localhost:11434"
                  className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="data-label">OLLAMA MODEL</label>
                  <button
                    onClick={() => loadModels(llmConfig.provider)}
                    disabled={loadingModels}
                    className="text-[10px] font-mono text-ork-dim hover:text-ork-cyan flex items-center gap-1 transition-colors"
                  >
                    <span className={loadingModels ? "inline-block animate-spin" : ""}>↺</span>
                    {loadingModels ? "Loading..." : "Refresh"}
                  </button>
                </div>
                <ModelSelect
                  value={llmConfig.ollama_model}
                  options={llmModels}
                  onChange={(v) => setLlmConfig((c) => ({ ...c, ollama_model: v }))}
                  placeholder="Select a model..."
                />
              </div>
            </>
          ) : (
            <>
              <div>
                <label className="data-label block mb-1.5">BASE URL</label>
                <input
                  type="text"
                  value={llmConfig.openai_base_url}
                  onChange={(e) => setLlmConfig((c) => ({ ...c, openai_base_url: e.target.value }))}
                  placeholder="https://api.mistral.ai/v1"
                  className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="data-label">MODEL</label>
                  <button
                    onClick={() => loadModels(llmConfig.provider)}
                    disabled={loadingModels}
                    className="text-[10px] font-mono text-ork-dim hover:text-ork-cyan flex items-center gap-1 transition-colors"
                  >
                    <span className={loadingModels ? "inline-block animate-spin" : ""}>↺</span>
                    {loadingModels ? "Loading..." : "Refresh"}
                  </button>
                </div>
                <ModelSelect
                  value={llmConfig.openai_model}
                  options={llmModels}
                  onChange={(v) => setLlmConfig((c) => ({ ...c, openai_model: v }))}
                  placeholder="Select a model..."
                />
              </div>
            </>
          )}
        </div>

        {/* API Key */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1.5">
            <label className="data-label">API KEY</label>
            {llmApiKeySet && (
              <span className="text-[9px] font-mono text-ork-green bg-ork-green/10 border border-ork-green/20 rounded px-1.5 py-0.5">CONFIGURED</span>
            )}
          </div>
          <input
            type="password"
            value={llmApiKey}
            onChange={(e) => setLlmApiKey(e.target.value)}
            placeholder={llmApiKeySet ? "Leave empty to keep current key" : "Enter API key…"}
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
          />
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleSaveLlmConfig}
            disabled={savingLlm}
            className="px-4 py-1.5 text-[10px] font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 hover:bg-ork-cyan/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {savingLlm ? "Saving..." : "Save Config"}
          </button>
          {llmSaved && (
            <span className="text-[10px] font-mono text-ork-green">✓ Saved</span>
          )}
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

function ModelSelect({ value, options, onChange, placeholder }: {
  value: string;
  options: string[];
  onChange: (v: string) => void;
  placeholder: string;
}) {
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState(false);

  const filtered = search
    ? options.filter((o) => o.toLowerCase().includes(search.toLowerCase()))
    : options;

  return (
    <div className="relative">
      <input
        type="text"
        value={open ? search : value || ""}
        onChange={(e) => { setSearch(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder={placeholder}
        className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
      />
      {open && <div className="fixed inset-0 z-40" onClick={() => { setOpen(false); setSearch(""); }} />}
      {open && (
        <div className="absolute z-50 w-full mt-1 max-h-48 overflow-y-auto bg-ork-surface border border-ork-border rounded shadow-lg">
          {filtered.length === 0 && (
            <p className="px-3 py-2 text-xs font-mono text-ork-dim">
              {options.length === 0 ? "Click Refresh to load models" : "No models found"}
            </p>
          )}
          {filtered.map((m) => (
            <button
              key={m}
              onClick={() => { onChange(m); setOpen(false); setSearch(""); }}
              className={`w-full text-left px-3 py-1.5 text-xs font-mono hover:bg-ork-hover transition-colors ${
                m === value ? "text-ork-cyan bg-ork-cyan/5" : "text-ork-text"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
