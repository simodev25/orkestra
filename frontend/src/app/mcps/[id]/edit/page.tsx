"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  getMcp,
  updateMcp,
  listAgentIds,
} from "@/lib/mcp/service";
import type {
  McpEffectType,
  McpCriticality,
  McpCostProfile,
  McpUpdatePayload,
  McpDefinition,
} from "@/lib/mcp/types";
import { EFFECT_TYPE_META, STATUS_META } from "@/lib/mcp/types";

// ────────────────────────────────────────────────────────────
// Constants
// ────────────────────────────────────────────────────────────

const EFFECT_TYPES: McpEffectType[] = ["read", "search", "compute", "generate", "validate", "write", "act"];
const CRITICALITIES: McpCriticality[] = ["low", "medium", "high"];
const COST_PROFILES: McpCostProfile[] = ["low", "medium", "high", "variable"];
const RETRY_POLICIES = ["none", "retry_once", "retry_twice", "standard", "aggressive"];

const EFFECT_BADGE_COLORS: Record<string, string> = {
  cyan: "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/25",
  purple: "bg-ork-purple/15 text-ork-purple border-ork-purple/25",
  green: "bg-ork-green/15 text-ork-green border-ork-green/25",
  amber: "bg-ork-amber/15 text-ork-amber border-ork-amber/25",
  red: "bg-ork-red/15 text-ork-red border-ork-red/25",
};

// ────────────────────────────────────────────────────────────
// Shared input class
// ────────────────────────────────────────────────────────────

const INPUT_CLS =
  "w-full bg-ork-bg border border-ork-border rounded-lg px-4 py-3 text-sm text-ork-text placeholder:text-ork-dim/50 font-mono focus:outline-none focus:border-ork-cyan/40 focus:ring-1 focus:ring-ork-cyan/20 transition-colors";

const SELECT_CLS = `${INPUT_CLS} appearance-none`;

const READONLY_CLS =
  "w-full bg-ork-bg/50 border border-ork-dim/30 rounded-lg px-4 py-3 text-sm text-ork-dim font-mono cursor-not-allowed";

// ────────────────────────────────────────────────────────────
// Page
// ────────────────────────────────────────────────────────────

export default function EditMcpPage() {
  const params = useParams();
  const id = params.id as string;

  // Data loading
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [mcp, setMcp] = useState<McpDefinition | null>(null);

  // Form state
  const [name, setName] = useState("");
  const [version, setVersion] = useState("");
  const [owner, setOwner] = useState("");

  const [purpose, setPurpose] = useState("");
  const [description, setDescription] = useState("");

  const [effectType, setEffectType] = useState<McpEffectType>("read");
  const [criticality, setCriticality] = useState<McpCriticality>("low");
  const [approvalRequired, setApprovalRequired] = useState(false);
  const [auditRequired, setAuditRequired] = useState(false);

  const [inputContractRef, setInputContractRef] = useState("");
  const [outputContractRef, setOutputContractRef] = useState("");

  const [timeoutSeconds, setTimeoutSeconds] = useState(30);
  const [retryPolicy, setRetryPolicy] = useState("none");
  const [costProfile, setCostProfile] = useState<McpCostProfile>("low");

  const [allowedAgents, setAllowedAgents] = useState<string[]>([]);
  const [availableAgents, setAvailableAgents] = useState<string[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(true);

  // Submission state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Validation
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  // ── Load MCP + agents ──
  useEffect(() => {
    if (!id) return;

    Promise.all([getMcp(id), listAgentIds()])
      .then(([mcpData, agents]) => {
        setMcp(mcpData);
        setAvailableAgents(agents);

        // Populate form
        setName(mcpData.name);
        setVersion(mcpData.version || "");
        setOwner(mcpData.owner || "");
        setPurpose(mcpData.purpose);
        setDescription(mcpData.description || "");
        setEffectType(mcpData.effect_type);
        setCriticality(mcpData.criticality);
        setApprovalRequired(mcpData.approval_required);
        setAuditRequired(mcpData.audit_required);
        setInputContractRef(mcpData.input_contract_ref || "");
        setOutputContractRef(mcpData.output_contract_ref || "");
        setTimeoutSeconds(mcpData.timeout_seconds);
        setRetryPolicy(mcpData.retry_policy || "none");
        setCostProfile(mcpData.cost_profile);
        setAllowedAgents(mcpData.allowed_agents || []);
      })
      .catch((e) => setLoadError(e instanceof Error ? e.message : "Failed to load MCP"))
      .finally(() => {
        setLoading(false);
        setAgentsLoading(false);
      });
  }, [id]);

  // ── Helpers ──
  function markTouched(field: string) {
    setTouched((prev) => ({ ...prev, [field]: true }));
  }

  function toggleAgent(agentId: string) {
    setAllowedAgents((prev) =>
      prev.includes(agentId) ? prev.filter((a) => a !== agentId) : [...prev, agentId]
    );
  }

  function selectAllAgents() {
    setAllowedAgents([...availableAgents]);
  }

  function clearAgents() {
    setAllowedAgents([]);
  }

  const isValid = name.trim() !== "" && purpose.trim() !== "";

  // ── Submit ──
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched({ name: true, purpose: true });

    if (!isValid) return;

    setSubmitting(true);
    setError(null);
    setSaved(false);

    const payload: McpUpdatePayload = {
      name: name.trim(),
      purpose: purpose.trim(),
      effect_type: effectType,
      criticality,
      timeout_seconds: timeoutSeconds,
      retry_policy: retryPolicy,
      cost_profile: costProfile,
      approval_required: approvalRequired,
      audit_required: auditRequired,
      version: version.trim() || undefined,
      owner: owner.trim() || undefined,
      description: description.trim() || undefined,
      input_contract_ref: inputContractRef.trim() || undefined,
      output_contract_ref: outputContractRef.trim() || undefined,
      allowed_agents: allowedAgents.length > 0 ? allowedAgents : undefined,
    };

    try {
      const updated = await updateMcp(id, payload);
      setMcp(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save changes");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Loading state ──
  if (loading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="glass-panel p-12 text-center">
          <div className="text-ork-cyan font-mono text-sm animate-pulse">
            Loading MCP...
          </div>
          <p className="text-[10px] text-ork-dim font-mono mt-2">{id}</p>
        </div>
      </div>
    );
  }

  // ── Load error state ──
  if (loadError || !mcp) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="glass-panel p-8 text-center">
          <p className="text-ork-red font-mono text-sm mb-4">
            {loadError || "MCP not found"}
          </p>
          <Link
            href="/mcps"
            className="text-xs font-mono text-ork-dim hover:text-ork-muted transition-colors"
          >
            &larr; BACK TO CATALOG
          </Link>
        </div>
      </div>
    );
  }

  const statusMeta = STATUS_META[mcp.status] || { label: mcp.status, color: "dim" };
  const statusColor: Record<string, string> = {
    green: "text-ork-green",
    amber: "text-ork-amber",
    red: "text-ork-red",
    cyan: "text-ork-cyan",
    purple: "text-ork-purple",
    dim: "text-ork-dim",
  };

  // ── Render ──
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-wide">EDIT MCP</h1>
          <p className="text-xs text-ork-dim font-mono mt-0.5">
            Modify <span className="text-ork-cyan">{id}</span>
          </p>
        </div>
        <Link
          href={`/mcps/${id}`}
          className="text-xs font-mono text-ork-dim hover:text-ork-muted transition-colors"
        >
          &larr; BACK TO DETAIL
        </Link>
      </div>

      {/* Current Status Banner */}
      <div className="glass-panel p-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="data-label">CURRENT STATUS</span>
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono uppercase tracking-wider ${
              statusColor[statusMeta.color] || "text-ork-dim"
            }`}
          >
            <span
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: "currentColor" }}
            />
            {statusMeta.label}
          </span>
        </div>
        <Link
          href={`/mcps/${id}`}
          className="text-[10px] font-mono text-ork-dim hover:text-ork-cyan transition-colors"
        >
          Manage lifecycle &rarr;
        </Link>
      </div>

      {/* Error banner */}
      {error && (
        <div className="glass-panel p-3 border-ork-red/30 animate-fade-in">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      {/* Saved banner */}
      {saved && (
        <div className="glass-panel p-3 border-ork-green/30 animate-fade-in">
          <p className="text-xs font-mono text-ork-green">
            Changes saved successfully.
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* ──────────────── Section 1: Identity ──────────────── */}
        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title text-sm pb-3 border-b border-ork-border">
            1. Identity
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* MCP ID (read-only) */}
            <div className="space-y-1.5">
              <label className="data-label">
                MCP ID
              </label>
              <input
                type="text"
                value={id}
                readOnly
                className={READONLY_CLS}
              />
              <p className="text-[10px] text-ork-dim font-mono">
                Immutable identifier
              </p>
            </div>

            {/* Name */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-name">
                NAME <span className="text-ork-red">*</span>
              </label>
              <input
                id="mcp-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onBlur={() => markTouched("name")}
                placeholder="MCP Display Name"
                required
                className={`${INPUT_CLS} ${touched.name && !name.trim() ? "border-ork-red/50" : ""}`}
              />
            </div>

            {/* Version */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-version">
                VERSION
              </label>
              <input
                id="mcp-version"
                type="text"
                value={version}
                onChange={(e) => setVersion(e.target.value)}
                placeholder="1.0.0"
                className={INPUT_CLS}
              />
            </div>

            {/* Owner */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-owner">
                OWNER
              </label>
              <input
                id="mcp-owner"
                type="text"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
                placeholder="team-data-engineering"
                className={INPUT_CLS}
              />
            </div>
          </div>
        </section>

        {/* ──────────────── Section 2: Purpose ──────────────── */}
        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title text-sm pb-3 border-b border-ork-border">
            2. Purpose
          </h2>

          <div className="space-y-1.5">
            <label className="data-label" htmlFor="mcp-purpose">
              PURPOSE <span className="text-ork-red">*</span>
            </label>
            <input
              id="mcp-purpose"
              type="text"
              value={purpose}
              onChange={(e) => setPurpose(e.target.value)}
              onBlur={() => markTouched("purpose")}
              placeholder="One-line mission statement"
              required
              className={`${INPUT_CLS} ${touched.purpose && !purpose.trim() ? "border-ork-red/50" : ""}`}
            />
            <p className="text-[10px] text-ork-dim font-mono">
              One-line mission statement
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="data-label" htmlFor="mcp-description">
              DESCRIPTION
            </label>
            <textarea
              id="mcp-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Detailed description of what this MCP does"
              rows={4}
              className={`${INPUT_CLS} resize-y`}
            />
            <p className="text-[10px] text-ork-dim font-mono">
              Detailed description of what this MCP does
            </p>
          </div>
        </section>

        {/* ──────────────── Section 3: Governance ──────────────── */}
        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title text-sm pb-3 border-b border-ork-border">
            3. Governance
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Effect Type */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-effect-type">
                EFFECT TYPE <span className="text-ork-red">*</span>
              </label>
              <div className="flex items-center gap-3">
                <select
                  id="mcp-effect-type"
                  value={effectType}
                  onChange={(e) => setEffectType(e.target.value as McpEffectType)}
                  className={`${SELECT_CLS} flex-1`}
                >
                  {EFFECT_TYPES.map((et) => (
                    <option key={et} value={et}>
                      {EFFECT_TYPE_META[et].label}
                    </option>
                  ))}
                </select>
                <span
                  className={`inline-flex items-center px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider border rounded whitespace-nowrap ${
                    EFFECT_BADGE_COLORS[EFFECT_TYPE_META[effectType].color] || "bg-ork-dim/20 text-ork-muted border-ork-dim/30"
                  }`}
                >
                  {EFFECT_TYPE_META[effectType].label}
                </span>
              </div>
            </div>

            {/* Criticality */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-criticality">
                CRITICALITY
              </label>
              <select
                id="mcp-criticality"
                value={criticality}
                onChange={(e) => setCriticality(e.target.value as McpCriticality)}
                className={SELECT_CLS}
              >
                {CRITICALITIES.map((c) => (
                  <option key={c} value={c}>
                    {c.charAt(0).toUpperCase() + c.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Checkboxes */}
          <div className="flex flex-col gap-3 pt-1">
            <label className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={approvalRequired}
                onChange={(e) => setApprovalRequired(e.target.checked)}
                className="w-4 h-4 rounded border-ork-border bg-ork-bg text-ork-cyan focus:ring-ork-cyan/30 focus:ring-offset-0 accent-ork-cyan"
              />
              <span className="text-sm text-ork-muted group-hover:text-ork-text transition-colors">
                Requires human approval before execution
              </span>
            </label>
            <label className="flex items-center gap-3 cursor-pointer group">
              <input
                type="checkbox"
                checked={auditRequired}
                onChange={(e) => setAuditRequired(e.target.checked)}
                className="w-4 h-4 rounded border-ork-border bg-ork-bg text-ork-cyan focus:ring-ork-cyan/30 focus:ring-offset-0 accent-ork-cyan"
              />
              <span className="text-sm text-ork-muted group-hover:text-ork-text transition-colors">
                All invocations must be logged for audit
              </span>
            </label>
          </div>
        </section>

        {/* ──────────────── Section 4: Contracts ──────────────── */}
        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title text-sm pb-3 border-b border-ork-border">
            4. Contracts
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-input-contract">
                INPUT CONTRACT REF
              </label>
              <input
                id="mcp-input-contract"
                type="text"
                value={inputContractRef}
                onChange={(e) => setInputContractRef(e.target.value)}
                placeholder="schemas/input.json"
                className={INPUT_CLS}
              />
              <p className="text-[10px] text-ork-dim font-mono">
                Path to input JSON schema
              </p>
            </div>
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-output-contract">
                OUTPUT CONTRACT REF
              </label>
              <input
                id="mcp-output-contract"
                type="text"
                value={outputContractRef}
                onChange={(e) => setOutputContractRef(e.target.value)}
                placeholder="schemas/output.json"
                className={INPUT_CLS}
              />
              <p className="text-[10px] text-ork-dim font-mono">
                Path to output JSON schema
              </p>
            </div>
          </div>
        </section>

        {/* ──────────────── Section 5: Runtime ──────────────── */}
        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title text-sm pb-3 border-b border-ork-border">
            5. Runtime
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Timeout */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-timeout">
                TIMEOUT (SECONDS)
              </label>
              <input
                id="mcp-timeout"
                type="number"
                min={1}
                max={3600}
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(Number(e.target.value) || 30)}
                className={INPUT_CLS}
              />
            </div>

            {/* Retry Policy */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-retry">
                RETRY POLICY
              </label>
              <select
                id="mcp-retry"
                value={retryPolicy}
                onChange={(e) => setRetryPolicy(e.target.value)}
                className={SELECT_CLS}
              >
                {RETRY_POLICIES.map((rp) => (
                  <option key={rp} value={rp}>
                    {rp.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>

            {/* Cost Profile */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-cost">
                COST PROFILE
              </label>
              <select
                id="mcp-cost"
                value={costProfile}
                onChange={(e) => setCostProfile(e.target.value as McpCostProfile)}
                className={SELECT_CLS}
              >
                {COST_PROFILES.map((cp) => (
                  <option key={cp} value={cp}>
                    {cp.charAt(0).toUpperCase() + cp.slice(1)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </section>

        {/* ──────────────── Section 6: Allowed Agents ──────────────── */}
        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title text-sm pb-3 border-b border-ork-border">
            6. Allowed Agents
          </h2>

          {agentsLoading ? (
            <div className="text-sm text-ork-cyan font-mono animate-pulse py-3">
              Loading agents...
            </div>
          ) : availableAgents.length === 0 ? (
            <p className="text-xs text-ork-dim font-mono py-3">
              No agents available
            </p>
          ) : (
            <>
              {/* Toolbar */}
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={selectAllAgents}
                  className="px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider text-ork-muted bg-ork-bg border border-ork-border rounded hover:border-ork-cyan/30 hover:text-ork-cyan transition-colors"
                >
                  Select All
                </button>
                <button
                  type="button"
                  onClick={clearAgents}
                  className="px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider text-ork-muted bg-ork-bg border border-ork-border rounded hover:border-ork-red/30 hover:text-ork-red transition-colors"
                >
                  Clear
                </button>
                <span className="text-[10px] font-mono text-ork-dim ml-auto">
                  {allowedAgents.length} / {availableAgents.length} selected
                </span>
              </div>

              {/* Selected pills */}
              {allowedAgents.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {allowedAgents.map((agentId) => (
                    <span
                      key={agentId}
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono bg-ork-cyan/10 text-ork-cyan border border-ork-cyan/20 rounded-full"
                    >
                      {agentId}
                      <button
                        type="button"
                        onClick={() => toggleAgent(agentId)}
                        className="hover:text-ork-red transition-colors"
                      >
                        <svg className="w-3 h-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </span>
                  ))}
                </div>
              )}

              {/* Checkbox list */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-1 max-h-52 overflow-y-auto rounded-lg bg-ork-bg border border-ork-border p-3">
                {availableAgents.map((agentId) => (
                  <label
                    key={agentId}
                    className="flex items-center gap-2.5 py-1.5 px-2 rounded cursor-pointer hover:bg-ork-hover transition-colors"
                  >
                    <input
                      type="checkbox"
                      checked={allowedAgents.includes(agentId)}
                      onChange={() => toggleAgent(agentId)}
                      className="w-3.5 h-3.5 rounded border-ork-border bg-ork-bg accent-ork-cyan"
                    />
                    <span className="text-xs font-mono text-ork-muted">
                      {agentId}
                    </span>
                  </label>
                ))}
              </div>
            </>
          )}
        </section>

        {/* ──────────────── Submit ──────────────── */}
        <div className="pt-2">
          <button
            type="submit"
            disabled={submitting || !isValid}
            className="w-full sm:w-auto px-8 py-3 bg-ork-cyan/15 border border-ork-cyan/30 rounded-lg text-ork-cyan text-xs font-mono uppercase tracking-wider hover:bg-ork-cyan/25 hover:border-ork-cyan/50 disabled:opacity-40 disabled:cursor-not-allowed transition-all duration-200"
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <span className="w-3 h-3 border border-ork-cyan/40 border-t-ork-cyan rounded-full animate-spin" />
                SAVING...
              </span>
            ) : (
              "SAVE CHANGES"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
