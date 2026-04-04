"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  createMcp,
  listAgentIds,
} from "@/lib/mcp/service";
import type {
  McpEffectType,
  McpCriticality,
  McpCostProfile,
  McpCreatePayload,
} from "@/lib/mcp/types";
import { EFFECT_TYPE_META } from "@/lib/mcp/types";

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

// ────────────────────────────────────────────────────────────
// Page
// ────────────────────────────────────────────────────────────

export default function NewMcpPage() {
  // Form state
  const [mcpId, setMcpId] = useState("");
  const [name, setName] = useState("");
  const [version, setVersion] = useState("1.0.0");
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
  const [createdId, setCreatedId] = useState<string | null>(null);

  // Validation
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  // ── Load agent list ──
  useEffect(() => {
    listAgentIds()
      .then(setAvailableAgents)
      .catch(() => setAvailableAgents([]))
      .finally(() => setAgentsLoading(false));
  }, []);

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

  const isValid = mcpId.trim() !== "" && name.trim() !== "" && purpose.trim() !== "";

  // ── Submit ──
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setTouched({ mcp_id: true, name: true, purpose: true, effect_type: true });

    if (!isValid) return;

    setSubmitting(true);
    setError(null);

    const payload: McpCreatePayload = {
      id: mcpId.trim(),
      name: name.trim(),
      purpose: purpose.trim(),
      effect_type: effectType,
      criticality,
      timeout_seconds: timeoutSeconds,
      retry_policy: retryPolicy,
      cost_profile: costProfile,
      approval_required: approvalRequired,
      audit_required: auditRequired,
      version: version.trim() || "1.0.0",
    };

    if (description.trim()) payload.description = description.trim();
    if (owner.trim()) payload.owner = owner.trim();
    if (inputContractRef.trim()) payload.input_contract_ref = inputContractRef.trim();
    if (outputContractRef.trim()) payload.output_contract_ref = outputContractRef.trim();
    if (allowedAgents.length > 0) payload.allowed_agents = allowedAgents;

    try {
      const created = await createMcp(payload);
      setCreatedId(created.id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create MCP");
    } finally {
      setSubmitting(false);
    }
  }

  // ── Success state ──
  if (createdId) {
    return (
      <div className="p-6 max-w-3xl mx-auto animate-fade-in">
        <div className="glass-panel p-10 text-center glow-cyan">
          <div className="w-14 h-14 rounded-full border-2 border-ork-green/40 mx-auto flex items-center justify-center mb-4">
            <svg className="w-7 h-7 text-ork-green" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
          </div>
          <h2 className="section-title text-sm mb-2">MCP CREATED</h2>
          <p className="text-sm text-ork-muted mb-1">
            <span className="font-mono text-ork-cyan">{createdId}</span> has been registered successfully.
          </p>
          <p className="text-xs text-ork-dim mb-8">
            The MCP starts in <span className="text-ork-amber">draft</span> status. Promote it through the lifecycle when ready.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href={`/mcps/${createdId}`}
              className="px-5 py-2.5 bg-ork-cyan/15 border border-ork-cyan/30 rounded-lg text-ork-cyan text-xs font-mono uppercase tracking-wider hover:bg-ork-cyan/25 hover:border-ork-cyan/50 transition-all duration-200"
            >
              View MCP Detail
            </Link>
            <Link
              href="/mcps"
              className="px-5 py-2.5 bg-ork-bg border border-ork-border rounded-lg text-ork-muted text-xs font-mono uppercase tracking-wider hover:border-ork-dim transition-colors"
            >
              Back to Catalog
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ── Render ──
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold tracking-wide">ADD MCP</h1>
          <p className="text-xs text-ork-dim font-mono mt-0.5">
            Register a new Model Context Protocol
          </p>
        </div>
        <Link
          href="/mcps"
          className="text-xs font-mono text-ork-dim hover:text-ork-muted transition-colors"
        >
          &larr; BACK TO CATALOG
        </Link>
      </div>

      {/* Error banner */}
      {error && (
        <div className="glass-panel p-3 border-ork-red/30 animate-fade-in">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* ──────────────── Section 1: Identity ──────────────── */}
        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title text-sm pb-3 border-b border-ork-border">
            1. Identity
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* MCP ID */}
            <div className="space-y-1.5">
              <label className="data-label" htmlFor="mcp-id">
                MCP ID <span className="text-ork-red">*</span>
              </label>
              <input
                id="mcp-id"
                type="text"
                value={mcpId}
                onChange={(e) => setMcpId(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "_"))}
                onBlur={() => markTouched("mcp_id")}
                placeholder="insee_sirene_lookup"
                required
                className={`${INPUT_CLS} ${touched.mcp_id && !mcpId.trim() ? "border-ork-red/50" : ""}`}
              />
              <p className="text-[10px] text-ork-dim font-mono">
                Unique identifier, e.g. insee_sirene_lookup
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
                placeholder="INSEE SIRENE Lookup"
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
                placeholder="schemas/insee_sirene_input.json"
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
                placeholder="schemas/insee_sirene_output.json"
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
                CREATING...
              </span>
            ) : (
              "CREATE MCP"
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
