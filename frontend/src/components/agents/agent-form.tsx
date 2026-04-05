"use client";

import { useMemo, useState } from "react";
import type {
  AgentCreatePayload,
  AgentDefinition,
  AgentStatus,
  AgentUpdatePayload,
  McpCatalogSummary,
} from "@/lib/agent-registry/types";
import { StatusBadge } from "@/components/ui/status-badge";

const EFFECT_TYPES = ["read", "search", "compute", "generate", "validate", "write", "act"] as const;
const STATUS_OPTIONS: AgentStatus[] = [
  "draft",
  "designed",
  "tested",
  "registered",
  "active",
  "deprecated",
  "disabled",
  "archived",
];

type FormPayload = AgentCreatePayload | AgentUpdatePayload;

function parseCsv(input: string): string[] {
  return input
    .split(",")
    .map((item) => item.trim())
    .filter((item) => item.length > 0);
}

function toCsv(values: string[] | null | undefined): string {
  if (!values || values.length === 0) return "";
  return values.join(", ");
}

function agentIdFromName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

interface AgentFormProps {
  mode: "create" | "edit";
  initial?: AgentDefinition;
  availableMcps: McpCatalogSummary[];
  availableSkills?: string[];
  submitLabel: string;
  saving: boolean;
  onSubmit: (payload: FormPayload) => Promise<void> | void;
}

export function AgentForm({
  mode,
  initial,
  availableMcps,
  availableSkills = [],
  submitLabel,
  saving,
  onSubmit,
}: AgentFormProps) {
  const [error, setError] = useState<string | null>(null);

  const [agentId, setAgentId] = useState(initial?.id ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [family, setFamily] = useState(initial?.family ?? "analyst");
  const [purpose, setPurpose] = useState(initial?.purpose ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [skills, setSkills] = useState(toCsv(initial?.skills));
  const [routingKeywords, setRoutingKeywords] = useState(
    toCsv((initial?.selection_hints?.routing_keywords as string[] | undefined) ?? []),
  );
  const [preferredWorkflows, setPreferredWorkflows] = useState(
    toCsv((initial?.selection_hints?.workflow_ids as string[] | undefined) ?? []),
  );
  const [requiresGroundedEvidence, setRequiresGroundedEvidence] = useState(
    Boolean(initial?.selection_hints?.requires_grounded_evidence ?? true),
  );
  const [selectionUseCaseHint, setSelectionUseCaseHint] = useState(
    String(initial?.selection_hints?.use_case_hint ?? ""),
  );
  const [allowedMcps, setAllowedMcps] = useState<string[]>(initial?.allowed_mcps ?? []);
  const [forbiddenEffects, setForbiddenEffects] = useState<string[]>(initial?.forbidden_effects ?? ["act"]);
  const [inputContractRef, setInputContractRef] = useState(initial?.input_contract_ref ?? "");
  const [outputContractRef, setOutputContractRef] = useState(initial?.output_contract_ref ?? "");
  const [criticality, setCriticality] = useState(initial?.criticality ?? "medium");
  const [costProfile, setCostProfile] = useState(initial?.cost_profile ?? "medium");
  const [limitations, setLimitations] = useState(toCsv(initial?.limitations));
  const [promptRef, setPromptRef] = useState(initial?.prompt_ref ?? "");
  const [promptContent, setPromptContent] = useState(initial?.prompt_content ?? "");
  const [skillsRef, setSkillsRef] = useState(initial?.skills_ref ?? "");
  const [skillsContent, setSkillsContent] = useState(initial?.skills_content ?? "");
  const [version, setVersion] = useState(initial?.version ?? "1.0.0");
  const [status, setStatus] = useState<AgentStatus>(initial?.status ?? "draft");
  const [owner, setOwner] = useState(initial?.owner ?? "");
  const [lastTestStatus, setLastTestStatus] = useState(initial?.last_test_status ?? "not_tested");
  const [usageCount, setUsageCount] = useState(initial?.usage_count ?? 0);

  const unknownAllowed = useMemo(() => {
    const knownIds = new Set(availableMcps.map((m) => m.id));
    return allowedMcps.filter((m) => !knownIds.has(m));
  }, [allowedMcps, availableMcps]);

  function toggleAllowedMcp(mcpId: string) {
    setAllowedMcps((prev) => (prev.includes(mcpId) ? prev.filter((x) => x !== mcpId) : [...prev, mcpId]));
  }

  function toggleForbiddenEffect(effectType: string) {
    setForbiddenEffects((prev) =>
      prev.includes(effectType) ? prev.filter((x) => x !== effectType) : [...prev, effectType],
    );
  }

  function validate(): string[] {
    const issues: string[] = [];
    const normalizedId = (mode === "create" ? agentId : initial?.id ?? agentId).trim();

    if (!/^[a-z0-9][a-z0-9_-]{1,99}$/.test(normalizedId)) {
      issues.push("`agent_id` must match ^[a-z0-9][a-z0-9_-]{1,99}$");
    }
    if (!name.trim()) issues.push("`name` is required");
    if (purpose.trim().length < 10) issues.push("`purpose` must be at least 10 chars");
    if (parseCsv(skills).length < 1) issues.push("at least one `skill` is required");
    if (!promptContent.trim()) issues.push("`prompt_content` is required");
    if (!skillsContent.trim()) issues.push("`skills_content` is required");
    if (parseCsv(limitations).length < 1) issues.push("at least one `limitation` is required");
    if (status === "active") issues.push("status cannot be `active` directly from design flow");
    if (unknownAllowed.length > 0) issues.push("`allowed_mcps` contains MCP IDs not in catalog");
    return issues;
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const issues = validate();
    if (issues.length > 0) {
      setError(issues.join(" | "));
      return;
    }
    setError(null);

    const selection_hints: Record<string, string | boolean | string[]> = {
      routing_keywords: parseCsv(routingKeywords),
      workflow_ids: parseCsv(preferredWorkflows),
      requires_grounded_evidence: requiresGroundedEvidence,
      use_case_hint: selectionUseCaseHint.trim(),
    };

    const payloadBase: AgentCreatePayload = {
      id: mode === "create" ? agentId.trim() : initial?.id ?? agentId.trim(),
      name: name.trim(),
      family: family.trim(),
      purpose: purpose.trim(),
      description: description.trim() || null,
      skills: parseCsv(skills),
      selection_hints,
      allowed_mcps: allowedMcps,
      forbidden_effects: forbiddenEffects,
      input_contract_ref: inputContractRef.trim() || null,
      output_contract_ref: outputContractRef.trim() || null,
      criticality: criticality.trim(),
      cost_profile: costProfile.trim(),
      limitations: parseCsv(limitations),
      prompt_ref: promptRef.trim() || null,
      prompt_content: promptContent.trim(),
      skills_ref: skillsRef.trim() || null,
      skills_content: skillsContent.trim(),
      version: version.trim() || "1.0.0",
      status,
      owner: owner.trim() || null,
      last_test_status: lastTestStatus.trim() || "not_tested",
      usage_count: Number.isFinite(usageCount) ? usageCount : 0,
    };

    if (mode === "create") {
      await onSubmit(payloadBase);
      return;
    }

    const { id: _id, ...updatePayload } = payloadBase;
    await onSubmit(updatePayload);
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      {error && (
        <div className="glass-panel p-3 border border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">1. Identity</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <p className="data-label">agent_id</p>
            <input
              value={agentId}
              onChange={(e) => setAgentId(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "_"))}
              placeholder="company_legal_lookup_agent"
              disabled={mode === "edit"}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono disabled:opacity-60"
            />
          </div>
          <div>
            <p className="data-label">name</p>
            <input
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (mode === "create" && !agentId.trim()) {
                  setAgentId(agentIdFromName(e.target.value));
                }
              }}
              placeholder="Company Legal Lookup Agent"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
            />
          </div>
          <div>
            <p className="data-label">family</p>
            <input
              value={family}
              onChange={(e) => setFamily(e.target.value)}
              placeholder="analyst"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <p className="data-label">version</p>
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <p className="data-label">status</p>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </div>
          <div>
            <p className="data-label">owner</p>
            <input
              value={owner}
              onChange={(e) => setOwner(e.target.value)}
              placeholder="team-risk-ops"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">2. Mission</h2>
        <div className="space-y-2">
          <p className="data-label">purpose</p>
          <input
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder="Find all legal and regulatory data about a company."
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
          />
          <p className="data-label">description</p>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">3. Skills</h2>
        <p className="data-label">skills (comma separated)</p>
        <input
          value={skills}
          onChange={(e) => setSkills(e.target.value)}
          placeholder="evidence_collection, entity_resolution, source_cross_check"
          className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          list="available-skills-list"
        />
        {availableSkills.length > 0 && (
          <datalist id="available-skills-list">
            {availableSkills.map((skill) => (
              <option key={skill} value={skill} />
            ))}
          </datalist>
        )}
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">4. Selection logic</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <p className="data-label">selection_hints.routing_keywords</p>
            <input
              value={routingKeywords}
              onChange={(e) => setRoutingKeywords(e.target.value)}
              placeholder="company, legal, registry, compliance"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <p className="data-label">selection_hints.workflow_ids</p>
            <input
              value={preferredWorkflows}
              onChange={(e) => setPreferredWorkflows(e.target.value)}
              placeholder="credit_review_default, due_diligence_v1"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <p className="data-label">selection_hints.use_case_hint</p>
            <input
              value={selectionUseCaseHint}
              onChange={(e) => setSelectionUseCaseHint(e.target.value)}
              placeholder="company intelligence"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
            />
          </div>
          <label className="flex items-center gap-2 mt-6 text-sm font-mono">
            <input
              type="checkbox"
              checked={requiresGroundedEvidence}
              onChange={(e) => setRequiresGroundedEvidence(e.target.checked)}
            />
            selection_hints.requires_grounded_evidence
          </label>
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">5. MCP permissions</h2>
        <p className="text-xs font-mono text-ork-dim">
          Select only MCPs available in catalog. Unknown MCP IDs are blocked at validation.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-52 overflow-y-auto border border-ork-border rounded p-2">
          {availableMcps.map((mcp) => {
            const checked = allowedMcps.includes(mcp.id);
            return (
              <label key={mcp.id} className="flex items-start gap-2 text-xs font-mono">
                <input type="checkbox" checked={checked} onChange={() => toggleAllowedMcp(mcp.id)} />
                <span>
                  <span className="text-ork-text">{mcp.name}</span>
                  <span className="text-ork-dim"> ({mcp.id})</span>
                  <span className="ml-2 text-ork-dim">{mcp.effect_type}</span>
                </span>
              </label>
            );
          })}
        </div>
        <div className="space-y-2">
          <p className="data-label">forbidden_effects</p>
          <div className="flex flex-wrap gap-2">
            {EFFECT_TYPES.map((effect) => {
              const on = forbiddenEffects.includes(effect);
              return (
                <button
                  key={effect}
                  type="button"
                  onClick={() => toggleForbiddenEffect(effect)}
                  className={`px-2 py-1 text-xs font-mono rounded border ${
                    on
                      ? "border-ork-red/40 text-ork-red bg-ork-red/10"
                      : "border-ork-border text-ork-muted"
                  }`}
                >
                  {effect}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">6. Contracts</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <p className="data-label">input_contract_ref</p>
            <input
              value={inputContractRef}
              onChange={(e) => setInputContractRef(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
          <div>
            <p className="data-label">output_contract_ref</p>
            <input
              value={outputContractRef}
              onChange={(e) => setOutputContractRef(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">7. Prompt</h2>
        <div>
          <p className="data-label">prompt_ref</p>
          <input
            value={promptRef}
            onChange={(e) => setPromptRef(e.target.value)}
            placeholder="prompts/company_lookup.v1.md"
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono mb-2"
          />
          <p className="data-label">prompt_content</p>
          <textarea
            value={promptContent}
            onChange={(e) => setPromptContent(e.target.value)}
            rows={8}
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">8. Skills file</h2>
        <div>
          <p className="data-label">skills_ref</p>
          <input
            value={skillsRef}
            onChange={(e) => setSkillsRef(e.target.value)}
            placeholder="skills/company_lookup.skills.md"
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono mb-2"
          />
          <p className="data-label">skills_content</p>
          <textarea
            value={skillsContent}
            onChange={(e) => setSkillsContent(e.target.value)}
            rows={6}
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">9. Limits & governance</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <p className="data-label">criticality</p>
            <select
              value={criticality}
              onChange={(e) => setCriticality(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            >
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="critical">critical</option>
            </select>
          </div>
          <div>
            <p className="data-label">cost_profile</p>
            <select
              value={costProfile}
              onChange={(e) => setCostProfile(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            >
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="variable">variable</option>
            </select>
          </div>
          <div>
            <p className="data-label">last_test_status</p>
            <select
              value={lastTestStatus}
              onChange={(e) => setLastTestStatus(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            >
              <option value="not_tested">not_tested</option>
              <option value="passed">passed</option>
              <option value="failed">failed</option>
              <option value="partial">partial</option>
            </select>
          </div>
        </div>
        <div>
          <p className="data-label">limitations (comma separated)</p>
          <input
            value={limitations}
            onChange={(e) => setLimitations(e.target.value)}
            placeholder="no direct write actions, escalate low-confidence outputs"
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">10. Lifecycle / ownership</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <p className="data-label">status preview</p>
            <div className="mt-1">
              <StatusBadge status={status} />
            </div>
          </div>
          <div>
            <p className="data-label">usage_count</p>
            <input
              type="number"
              min={0}
              value={usageCount}
              onChange={(e) => setUsageCount(Number(e.target.value))}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>
        </div>
      </section>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="px-4 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 disabled:opacity-50"
        >
          {saving ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
