"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import type {
  AgentCreatePayload,
  AgentDefinition,
  AgentStatus,
  AgentUpdatePayload,
  McpCatalogSummary,
} from "@/lib/agent-registry/types";
import { request } from "@/lib/api-client";
import type { FamilyDefinition, SkillDefinition } from "@/lib/families/types";
import { listSkillsByFamily } from "@/lib/families/service";
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
  availableFamilies: FamilyDefinition[];
  submitLabel: string;
  saving: boolean;
  onSubmit: (payload: FormPayload) => Promise<void> | void;
}

export function AgentForm({
  mode,
  initial,
  availableMcps,
  availableFamilies,
  submitLabel,
  saving,
  onSubmit,
}: AgentFormProps) {
  const [error, setError] = useState<string | null>(null);

  const [agentId, setAgentId] = useState(initial?.id ?? "");
  const [name, setName] = useState(initial?.name ?? "");
  const [familyId, setFamilyId] = useState(initial?.family_id ?? "");
  const [purpose, setPurpose] = useState(initial?.purpose ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [skillIds, setSkillIds] = useState<string[]>(initial?.skill_ids ?? []);
  const [skillsInput, setSkillsInput] = useState("");
  const [familySkills, setFamilySkills] = useState<SkillDefinition[]>([]);
  const [skillWarning, setSkillWarning] = useState<string | null>(null);
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
  const [promptContent, setPromptContent] = useState(initial?.prompt_content ?? "");
  const [skillsContent, setSkillsContent] = useState(initial?.skills_content ?? "");
  const [soulContent, setSoulContent] = useState(initial?.soul_content ?? "");
  const [version, setVersion] = useState(initial?.version ?? "1.0.0");
  const [status, setStatus] = useState<AgentStatus>(initial?.status ?? "draft");
  const [owner, setOwner] = useState(initial?.owner ?? "");
  const [lastTestStatus, setLastTestStatus] = useState(initial?.last_test_status ?? "not_tested");
  const [usageCount, setUsageCount] = useState(initial?.usage_count ?? 0);
  const [llmProvider, setLlmProvider] = useState(initial?.llm_provider ?? "");
  const [llmModel, setLlmModel] = useState(initial?.llm_model ?? "");
  const [allowCodeExecution, setAllowCodeExecution] = useState(initial?.allow_code_execution ?? false);
  const [allowedBuiltinTools, setAllowedBuiltinTools] = useState<string[]>(initial?.allowed_builtin_tools ?? []);
  const [pipelineAgentIds, setPipelineAgentIds] = useState<string[]>(initial?.pipeline_agent_ids ?? []);
  const [routingMode, setRoutingMode] = useState<string>(initial?.routing_mode ?? "sequential");
  const [availableModels, setAvailableModels] = useState<string[]>([]);

  useEffect(() => {
    if (initial?.llm_provider) {
      request<{ models: any[] }>(`/api/agents/llm-models/${initial.llm_provider}`)
        .then(data => setAvailableModels((data.models || []).map((m: any) => typeof m === "string" ? m : m.name)))
        .catch(() => setAvailableModels([]));
    }
  }, []);

  useEffect(() => {
    if (!familyId) {
      setFamilySkills([]);
      return;
    }
    listSkillsByFamily(familyId)
      .then((data) => {
        setFamilySkills(data);
        const allowedIds = new Set(data.map((s) => s.skill_id));
        const incompatible = skillIds.filter((s) => !allowedIds.has(s));
        if (incompatible.length > 0) {
          setSkillIds(skillIds.filter((s) => allowedIds.has(s)));
          setSkillWarning(`Skills removed (incompatible with ${familyId}): ${incompatible.join(", ")}`);
        } else {
          setSkillWarning(null);
        }
      })
      .catch(() => setFamilySkills([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [familyId]);

  // Auto-generate skills_content when skills selection changes
  useEffect(() => {
    if (familySkills.length === 0 || skillIds.length === 0) return;
    const selected = familySkills.filter((s) => skillIds.includes(s.skill_id));
    if (selected.length === 0) return;
    const content = selected
      .map((s) => {
        const lines = [`## ${s.label} (${s.skill_id})`];
        if (s.description) lines.push(s.description);
        if (s.behavior_templates?.length) {
          lines.push("\nBehavior:");
          s.behavior_templates.forEach((t) => lines.push(`- ${t}`));
        }
        if (s.output_guidelines?.length) {
          lines.push("\nOutput guidelines:");
          s.output_guidelines.forEach((g) => lines.push(`- ${g}`));
        }
        return lines.join("\n");
      })
      .join("\n\n---\n\n");
    setSkillsContent(content);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skillIds, familySkills]);

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
    if (skillIds.length < 1) issues.push("at least one `skill` is required");
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
      family_id: familyId.trim(),
      purpose: purpose.trim(),
      description: description.trim() || null,
      skill_ids: skillIds,
      selection_hints,
      allowed_mcps: allowedMcps,
      forbidden_effects: forbiddenEffects,
      input_contract_ref: inputContractRef.trim() || null,
      output_contract_ref: outputContractRef.trim() || null,
      criticality: criticality.trim(),
      cost_profile: costProfile.trim(),
      limitations: parseCsv(limitations),
      prompt_content: promptContent.trim(),
      skills_content: skillsContent.trim(),
      soul_content: soulContent.trim() || null,
      llm_provider: llmProvider.trim() || null,
      llm_model: llmModel.trim() || null,
      allow_code_execution: allowCodeExecution,
      allowed_builtin_tools: allowedBuiltinTools.length > 0 ? allowedBuiltinTools : null,
      pipeline_agent_ids: isOrchestrator ? pipelineAgentIds : [],
      routing_mode: isOrchestrator ? routingMode : "sequential",
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

  const isOrchestrator = familyId === "orchestration";

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
            <label htmlFor="agent-id" className="data-label">agent_id</label>
            <input
              id="agent-id"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "_"))}
              placeholder="company_legal_lookup_agent"
              disabled={mode === "edit"}
              className="field w-full disabled:opacity-60"
            />
          </div>
          <div>
            <label htmlFor="agent-name" className="data-label">name</label>
            <input
              id="agent-name"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (mode === "create" && !agentId.trim()) {
                  setAgentId(agentIdFromName(e.target.value));
                }
              }}
              placeholder="Company Legal Lookup Agent"
              className="field w-full"
            />
          </div>
          <div>
            <label htmlFor="agent-family" className="data-label">family</label>
            <select
              id="agent-family"
              value={familyId}
              onChange={(e) => setFamilyId(e.target.value)}
              className="field w-full"
            >
              <option value="">Select a family...</option>
              {availableFamilies.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.label} ({f.id})
                </option>
              ))}
            </select>
          </div>
          <div>
            <p className="data-label">version</p>
            <input
              value={version}
              onChange={(e) => setVersion(e.target.value)}
              className="field w-full"
            />
          </div>
          <div>
            <p className="data-label">status</p>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              className="field w-full"
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
              className="field w-full"
            />
          </div>
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">2. Mission</h2>
        <div className="space-y-2">
          <label htmlFor="agent-purpose" className="data-label">purpose</label>
          <input
            id="agent-purpose"
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder="Find all legal and regulatory data about a company."
            className="field w-full"
          />
          <label htmlFor="agent-description" className="data-label">description</label>
          <textarea
            id="agent-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            className="field w-full"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">3. Skills</h2>
        {skillWarning && (
          <div className="p-2 border border-ork-amber/30 rounded text-xs font-mono text-ork-amber">
            {skillWarning}
          </div>
        )}
        {!familyId ? (
          <p className="dim text-xs font-mono">Select a family first to see available skills.</p>
        ) : familySkills.length === 0 ? (
          <p className="dim text-xs font-mono">No skills available for this family.</p>
        ) : (
          <>
            <p className="data-label">available skills for {familyId}</p>
            <input
              value={skillsInput}
              onChange={(e) => setSkillsInput(e.target.value)}
              placeholder="Filter skills…"
              className="field w-full"
            />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5 max-h-52 overflow-y-auto border border-ork-border rounded p-2">
              {familySkills
                .filter((s) => {
                  const q = skillsInput.toLowerCase();
                  if (!q) return true;
                  return s.skill_id.toLowerCase().includes(q) || s.label.toLowerCase().includes(q);
                })
                .map((skill) => {
                  const checked = skillIds.includes(skill.skill_id);
                  return (
                    <label
                      key={skill.skill_id}
                      className={`flex items-start gap-2 text-xs font-mono p-1.5 rounded cursor-pointer transition-colors ${
                        checked ? "bg-ork-cyan/10 text-ork-cyan" : "text-ork-muted hover:bg-ork-hover"
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => {
                          if (checked) {
                            setSkillIds(skillIds.filter((s) => s !== skill.skill_id));
                          } else {
                            setSkillIds([...skillIds, skill.skill_id]);
                          }
                        }}
                        className="mt-0.5 accent-ork-cyan"
                      />
                      <span>
                        <span className="text-ork-text font-semibold">{skill.label}</span>
                        <span className="text-ork-dim"> ({skill.skill_id})</span>
                        {skill.description && (
                          <span className="block text-[10px] text-ork-dim mt-0.5 leading-tight">
                            {skill.description.length > 100
                              ? skill.description.slice(0, 100) + "…"
                              : skill.description}
                          </span>
                        )}
                      </span>
                    </label>
                  );
                })}
            </div>
            <p className="dim text-[10px] font-mono">
              {skillIds.length} skill{skillIds.length !== 1 ? "s" : ""} selected
            </p>
          </>
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
              className="field w-full"
            />
          </div>
          <div>
            <p className="data-label">selection_hints.workflow_ids</p>
            <input
              value={preferredWorkflows}
              onChange={(e) => setPreferredWorkflows(e.target.value)}
              placeholder="credit_review_default, due_diligence_v1"
              className="field w-full"
            />
          </div>
          <div>
            <p className="data-label">selection_hints.use_case_hint</p>
            <input
              value={selectionUseCaseHint}
              onChange={(e) => setSelectionUseCaseHint(e.target.value)}
              placeholder="company intelligence"
              className="field w-full"
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

      {isOrchestrator && (
        <div className="form-section">
          <h2 className="section-title text-sm">5. Pipeline d&apos;agents</h2>

          {/* Routing mode toggle */}
          <div className="mb-4">
            <p className="data-label">mode de routage</p>
            <div className="flex gap-2 mt-1">
              {(["sequential", "dynamic"] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setRoutingMode(m)}
                  className={routingMode === m ? "btn btn--cyan" : "btn btn--ghost"}
                >
                  {m === "sequential" ? "Séquentiel (ordre fixe)" : "Dynamique (LLM choisit)"}
                </button>
              ))}
            </div>
            <p className="dim text-[10px] mt-1">
              {routingMode === "sequential"
                ? "Les agents sont appelés dans l'ordre défini ci-dessous."
                : "L'orchestrateur décide dynamiquement de l'ordre d'appel des agents."}
            </p>
          </div>

          {/* Agent pipeline list */}
          <div>
            <p className="data-label mb-2">agents dans le pipeline (glisser pour réordonner)</p>
            <PipelineAgentEditor
              agentIds={pipelineAgentIds}
              onChange={setPipelineAgentIds}
            />
          </div>
        </div>
      )}

      {!isOrchestrator && (
        <section className="glass-panel p-4 space-y-3">
          <h2 className="section-title text-sm">5. MCP permissions</h2>
          <p className="dim text-xs font-mono">
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
                    className={on ? "btn btn--red" : "btn btn--ghost"}
                  >
                    {effect}
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      )}

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">6. Contracts</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <p className="data-label">input_contract_ref</p>
            <input
              value={inputContractRef}
              onChange={(e) => setInputContractRef(e.target.value)}
              className="field w-full"
            />
          </div>
          <div>
            <p className="data-label">output_contract_ref</p>
            <input
              value={outputContractRef}
              onChange={(e) => setOutputContractRef(e.target.value)}
              className="field w-full"
            />
          </div>
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">7. Agent Prompt</h2>
        <div>
          <p className="data-label">prompt_content</p>
          <p className="dim text-[10px] font-mono mb-1">Agent-specific mission prompt (Layer 4 of the prompt builder)</p>
          <textarea
            value={promptContent}
            onChange={(e) => setPromptContent(e.target.value)}
            rows={8}
            className="field w-full"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">8. Skills Content</h2>
        <div>
          <p className="data-label">skills_content</p>
          <p className="dim text-[10px] font-mono mb-1">Auto-generated from selected skills. Edit only if needed.</p>
          <textarea
            value={skillsContent}
            onChange={(e) => setSkillsContent(e.target.value)}
            rows={6}
            className="field w-full"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">9. Soul</h2>
        <p className="dim text-xs font-mono">
          Optional soul content — overarching character, values and behavioural identity injected into this agent.
        </p>
        <div>
          <p className="data-label">soul_content</p>
          <textarea
            value={soulContent}
            onChange={(e) => setSoulContent(e.target.value)}
            rows={6}
            placeholder="You are a disciplined analyst who values accuracy above speed…"
            className="field w-full"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">10. LLM Configuration</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <div>
            <p className="data-label">provider</p>
            <select
              value={llmProvider}
              onChange={(e) => {
                setLlmProvider(e.target.value);
                setLlmModel("");
                setAvailableModels([]);
                if (e.target.value) {
                  request<{ models: any[] }>(`/api/agents/llm-models/${e.target.value}`)
                    .then(data => setAvailableModels((data.models || []).map((m: any) => typeof m === "string" ? m : m.name)))
                    .catch(() => setAvailableModels([]));
                }
              }}
              className="field w-full"
            >
              <option value="">Default (platform config)</option>
              <option value="ollama">Ollama</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
          <div>
            <p className="data-label">model</p>
            {availableModels.length > 0 ? (
              <select
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                className="field w-full"
              >
                <option value="">Select a model...</option>
                {availableModels.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <input
                value={llmModel}
                onChange={(e) => setLlmModel(e.target.value)}
                placeholder={llmProvider ? "Loading models..." : "Select a provider first"}
                disabled={!llmProvider}
                className="field w-full disabled:opacity-60"
              />
            )}
          </div>
        </div>
        <p className="dim text-[10px] font-mono">
          Leave empty to use the platform default LLM configuration.
        </p>
        {/* Built-in tool functions — unified toggle list */}
        {!isOrchestrator && <div className="pt-1 border-t border-ork-border/30 space-y-0">
          <p className="text-xs font-mono text-ork-text mb-2">Built-in tool functions</p>
          {([
            {
              name: "execute_python_code",
              desc: <>Enable <span className="text-ork-cyan">execute_python_code</span> — run Python, call external APIs. Requires platform toggle ON.</>,
              color: "bg-ork-amber",
              checked: allowCodeExecution,
              onToggle: () => setAllowCodeExecution((v) => !v),
            },
            {
              name: "execute_shell_command",
              desc: <>Enable <span className="text-ork-cyan">execute_shell_command</span> — run shell commands in an isolated sandbox.</>,
              color: "bg-ork-red",
              checked: allowedBuiltinTools.includes("execute_shell_command"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("execute_shell_command") ? p.filter((t) => t !== "execute_shell_command") : [...p, "execute_shell_command"]),
            },
            {
              name: "view_text_file",
              desc: <>Enable <span className="text-ork-cyan">view_text_file</span> — read files from the filesystem sandbox.</>,
              color: "bg-ork-green",
              checked: allowedBuiltinTools.includes("view_text_file"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("view_text_file") ? p.filter((t) => t !== "view_text_file") : [...p, "view_text_file"]),
            },
            {
              name: "write_text_file",
              desc: <>Enable <span className="text-ork-cyan">write_text_file</span> — write/overwrite files in the filesystem sandbox.</>,
              color: "bg-ork-green",
              checked: allowedBuiltinTools.includes("write_text_file"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("write_text_file") ? p.filter((t) => t !== "write_text_file") : [...p, "write_text_file"]),
            },
            {
              name: "insert_text_file",
              desc: <>Enable <span className="text-ork-cyan">insert_text_file</span> — insert text into files in the filesystem sandbox.</>,
              color: "bg-ork-green",
              checked: allowedBuiltinTools.includes("insert_text_file"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("insert_text_file") ? p.filter((t) => t !== "insert_text_file") : [...p, "insert_text_file"]),
            },
            {
              name: "dashscope_text_to_image",
              desc: <>Enable <span className="text-ork-cyan">dashscope_text_to_image</span> — generate images from text (DashScope).</>,
              color: "bg-ork-amber",
              checked: allowedBuiltinTools.includes("dashscope_text_to_image"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("dashscope_text_to_image") ? p.filter((t) => t !== "dashscope_text_to_image") : [...p, "dashscope_text_to_image"]),
            },
            {
              name: "dashscope_text_to_audio",
              desc: <>Enable <span className="text-ork-cyan">dashscope_text_to_audio</span> — generate audio from text (DashScope).</>,
              color: "bg-ork-amber",
              checked: allowedBuiltinTools.includes("dashscope_text_to_audio"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("dashscope_text_to_audio") ? p.filter((t) => t !== "dashscope_text_to_audio") : [...p, "dashscope_text_to_audio"]),
            },
            {
              name: "dashscope_image_to_text",
              desc: <>Enable <span className="text-ork-cyan">dashscope_image_to_text</span> — describe images (DashScope).</>,
              color: "bg-ork-amber",
              checked: allowedBuiltinTools.includes("dashscope_image_to_text"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("dashscope_image_to_text") ? p.filter((t) => t !== "dashscope_image_to_text") : [...p, "dashscope_image_to_text"]),
            },
            {
              name: "openai_text_to_image",
              desc: <>Enable <span className="text-ork-cyan">openai_text_to_image</span> — generate images from text (OpenAI).</>,
              color: "bg-ork-cyan",
              checked: allowedBuiltinTools.includes("openai_text_to_image"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("openai_text_to_image") ? p.filter((t) => t !== "openai_text_to_image") : [...p, "openai_text_to_image"]),
            },
            {
              name: "openai_text_to_audio",
              desc: <>Enable <span className="text-ork-cyan">openai_text_to_audio</span> — generate audio from text (OpenAI).</>,
              color: "bg-ork-cyan",
              checked: allowedBuiltinTools.includes("openai_text_to_audio"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("openai_text_to_audio") ? p.filter((t) => t !== "openai_text_to_audio") : [...p, "openai_text_to_audio"]),
            },
            {
              name: "openai_edit_image",
              desc: <>Enable <span className="text-ork-cyan">openai_edit_image</span> — edit images (OpenAI).</>,
              color: "bg-ork-cyan",
              checked: allowedBuiltinTools.includes("openai_edit_image"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("openai_edit_image") ? p.filter((t) => t !== "openai_edit_image") : [...p, "openai_edit_image"]),
            },
            {
              name: "openai_create_image_variation",
              desc: <>Enable <span className="text-ork-cyan">openai_create_image_variation</span> — create image variations (OpenAI).</>,
              color: "bg-ork-cyan",
              checked: allowedBuiltinTools.includes("openai_create_image_variation"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("openai_create_image_variation") ? p.filter((t) => t !== "openai_create_image_variation") : [...p, "openai_create_image_variation"]),
            },
            {
              name: "openai_image_to_text",
              desc: <>Enable <span className="text-ork-cyan">openai_image_to_text</span> — describe images (OpenAI).</>,
              color: "bg-ork-cyan",
              checked: allowedBuiltinTools.includes("openai_image_to_text"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("openai_image_to_text") ? p.filter((t) => t !== "openai_image_to_text") : [...p, "openai_image_to_text"]),
            },
            {
              name: "openai_audio_to_text",
              desc: <>Enable <span className="text-ork-cyan">openai_audio_to_text</span> — transcribe audio to text (OpenAI).</>,
              color: "bg-ork-cyan",
              checked: allowedBuiltinTools.includes("openai_audio_to_text"),
              onToggle: () => setAllowedBuiltinTools((p) => p.includes("openai_audio_to_text") ? p.filter((t) => t !== "openai_audio_to_text") : [...p, "openai_audio_to_text"]),
            },
          ] as { name: string; desc: React.ReactNode; color: string; checked: boolean; onToggle: () => void }[]).map(({ name, desc, color, checked, onToggle }) => (
            <div key={name} className="flex items-center justify-between py-1.5 border-b border-ork-border/20 last:border-0">
              <div className="flex-1 min-w-0 pr-4">
                <p className="dim text-[10px] font-mono leading-snug">{desc}</p>
              </div>
              <button
                type="button"
                onClick={onToggle}
                className={`shrink-0 relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none ${
                  checked ? color : "bg-ork-border"
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                    checked ? "translate-x-4" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>}
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">11. Limits & governance</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div>
            <p className="data-label">criticality</p>
            <select
              value={criticality}
              onChange={(e) => setCriticality(e.target.value)}
              className="field w-full"
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
              className="field w-full"
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
              className="field w-full"
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
            className="field w-full"
          />
        </div>
      </section>

      <section className="glass-panel p-4 space-y-3">
        <h2 className="section-title text-sm">12. Lifecycle / ownership</h2>
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
              className="field w-full"
            />
          </div>
        </div>
      </section>

      <div className="flex justify-end">
        <button
          type="submit"
          disabled={saving}
          className="btn btn--cyan disabled:opacity-50"
        >
          {saving ? "Saving..." : submitLabel}
        </button>
      </div>
    </form>
  );
}

// ── Inline pipeline editor ────────────────────────────────────────────────────

interface PipelineAgentEditorProps {
  agentIds: string[];
  onChange: (ids: string[]) => void;
}

function PipelineAgentEditor({ agentIds, onChange }: PipelineAgentEditorProps) {
  const [newId, setNewId] = useState("");
  const dragIdx = useRef<number | null>(null);

  function handleDragStart(idx: number) { dragIdx.current = idx; }
  function handleDrop(targetIdx: number) {
    const from = dragIdx.current;
    if (from === null || from === targetIdx) return;
    const next = [...agentIds];
    const [moved] = next.splice(from, 1);
    next.splice(targetIdx, 0, moved);
    onChange(next);
    dragIdx.current = null;
  }
  function removeAgent(id: string) { onChange(agentIds.filter((x) => x !== id)); }
  function addAgent() {
    const id = newId.trim();
    if (id && !agentIds.includes(id)) {
      onChange([...agentIds, id]);
      setNewId("");
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {agentIds.map((id, idx) => (
        <div
          key={id}
          draggable
          onDragStart={() => handleDragStart(idx)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => handleDrop(idx)}
          className="flex items-center gap-2 bg-ork-bg border border-ork-cyan rounded-md px-3 py-2 cursor-grab"
        >
          <span className="text-ork-dim text-sm select-none">⠿</span>
          <span className="bg-ork-cyan text-black text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0">{idx + 1}</span>
          <span className="text-xs text-ork-cyan font-mono flex-1">{id}</span>
          <button type="button" onClick={() => removeAgent(id)} className="text-ork-dim hover:text-red-400 text-xs">✕</button>
        </div>
      ))}
      <div className="flex gap-2">
        <input
          type="text"
          value={newId}
          onChange={(e) => setNewId(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addAgent(); }}}
          placeholder="agent_id à ajouter…"
          className="field flex-1"
        />
        <button
          type="button"
          onClick={addAgent}
          className="btn btn--ghost"
        >
          + Ajouter
        </button>
      </div>
    </div>
  );
}
