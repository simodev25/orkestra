"use client";

import { useEffect, useMemo, useState } from "react";
import {
  generateAgentDraft,
  saveGeneratedDraft,
} from "@/lib/agent-registry/service";
import type {
  AgentDefinition,
  AgentGenerationRequest,
  GeneratedAgentDraft,
  McpCatalogSummary,
} from "@/lib/agent-registry/types";
import { StatusBadge } from "@/components/ui/status-badge";
import { listFamilies, listSkills } from "@/lib/families/service";
import type { FamilyDefinition, SkillDefinition } from "@/lib/families/types";

function parseCsv(input: string): string[] {
  return input
    .split(",")
    .map((v) => v.trim())
    .filter((v) => v.length > 0);
}

function toCsv(values: string[] | null | undefined): string {
  if (!values || values.length === 0) return "";
  return values.join(", ");
}

interface GenerateAgentModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: (agent: AgentDefinition) => void;
}

export function GenerateAgentModal({ open, onClose, onSaved }: GenerateAgentModalProps) {
  const [request, setRequest] = useState<AgentGenerationRequest>({
    intent: "",
    use_case: "",
    target_workflow: "",
    criticality_target: "",
    preferred_family: "",
    preferred_skill_ids: [],
    preferred_output_style: "",
    preferred_mcp_scope: "",
    constraints: "",
    owner: "",
  });
  const [step, setStep] = useState<"intent" | "generating" | "review">("intent");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [source, setSource] = useState<string>("");
  const [availableMcps, setAvailableMcps] = useState<McpCatalogSummary[]>([]);
  const [draft, setDraft] = useState<GeneratedAgentDraft | null>(null);
  const [families, setFamilies] = useState<FamilyDefinition[]>([]);
  const [skills, setSkills] = useState<SkillDefinition[]>([]);

  useEffect(() => {
    let cancelled = false;
    if (!open) return;
    (async () => {
      try {
        const [familiesResp, skillsResp] = await Promise.all([
          listFamilies(false),
          listSkills(false),
        ]);
        if (cancelled) return;
        setFamilies(familiesResp.filter((f) => f.status === "active"));
        setSkills(skillsResp.filter((s) => (s.status || "active") === "active"));
      } catch {
        if (!cancelled) {
          setFamilies([]);
          setSkills([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const [skillIdsCsv, setSkillIdsCsv] = useState("");
  const [forbiddenEffectsCsv, setForbiddenEffectsCsv] = useState("");
  const [limitationsCsv, setLimitationsCsv] = useState("");
  const [routingKeywordsCsv, setRoutingKeywordsCsv] = useState("");
  const [workflowIdsCsv, setWorkflowIdsCsv] = useState("");

  const knownMcpIds = useMemo(() => new Set(availableMcps.map((m) => m.id)), [availableMcps]);

  if (!open) return null;

  function syncReviewFields(nextDraft: GeneratedAgentDraft) {
    setSkillIdsCsv(toCsv(nextDraft.skill_ids));
    setForbiddenEffectsCsv(toCsv(nextDraft.forbidden_effects));
    setLimitationsCsv(toCsv(nextDraft.limitations));
    setRoutingKeywordsCsv(toCsv((nextDraft.selection_hints?.routing_keywords as string[]) ?? []));
    setWorkflowIdsCsv(toCsv((nextDraft.selection_hints?.workflow_ids as string[]) ?? []));
  }

  async function runGeneration() {
    setStep("generating");
    setError(null);
    try {
      const response = await generateAgentDraft(request);
      setSource(response.source);
      setAvailableMcps(response.available_mcps);
      setDraft(response.draft);
      syncReviewFields(response.draft);
      setStep("review");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Generation failed");
      setStep("intent");
    }
  }

  function updateDraft(next: Partial<GeneratedAgentDraft>) {
    setDraft((prev) => (prev ? { ...prev, ...next } : prev));
  }

  function sourceLabel(value: string): string {
    if (value === "llm") return "AI-generated";
    if (value === "heuristic_template") return "Template draft";
    return value || "unknown";
  }

  function toggleMcp(mcpId: string) {
    if (!draft) return;
    const current = new Set(draft.allowed_mcps);
    if (current.has(mcpId)) current.delete(mcpId);
    else current.add(mcpId);
    updateDraft({ allowed_mcps: Array.from(current) });
  }

  function validateDraftForSave(current: GeneratedAgentDraft): string[] {
    const issues: string[] = [];
    if (!/^[a-z0-9][a-z0-9_-]{1,99}$/.test(current.agent_id)) issues.push("agent_id invalid");
    if (!current.name.trim()) issues.push("name required");
    if (!current.purpose.trim()) issues.push("purpose required");
    if (parseCsv(skillIdsCsv).length === 0) issues.push("at least one skill required");
    if (!current.prompt_content.trim()) issues.push("prompt_content required");
    if (!current.skills_content.trim()) issues.push("skills_content required");
    if (parseCsv(limitationsCsv).length === 0) issues.push("at least one limitation required");
    if (current.status === "active") issues.push("status cannot be active");
    const unknown = current.allowed_mcps.filter((id) => !knownMcpIds.has(id));
    if (unknown.length > 0) issues.push(`unknown MCP IDs: ${unknown.join(", ")}`);
    return issues;
  }

  async function saveDraft() {
    if (!draft) return;

    const normalizedSelectionHints: Record<string, string | boolean | string[]> = {
      ...draft.selection_hints,
      routing_keywords: parseCsv(routingKeywordsCsv),
      workflow_ids: parseCsv(workflowIdsCsv),
    };
    const normalized: GeneratedAgentDraft = {
      ...draft,
      skill_ids: parseCsv(skillIdsCsv),
      forbidden_effects: parseCsv(forbiddenEffectsCsv),
      limitations: parseCsv(limitationsCsv),
      selection_hints: normalizedSelectionHints,
      status: "draft",
    };

    const issues = validateDraftForSave(normalized);
    if (issues.length > 0) {
      setError(issues.join(" | "));
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const created = await saveGeneratedDraft(normalized);
      onSaved(created);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save generated draft");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Generate Agent with AI" className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm p-4 md:p-8 overflow-y-auto">
      <div className="max-w-6xl mx-auto glass-panel border border-ork-border">
        <div className="p-4 border-b border-ork-border flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">Generate Agent</h2>
            <p className="text-xs font-mono text-ork-dim">
              Describe what this agent should do. AI will draft it for you, with a template fallback when needed.
            </p>
          </div>
          <button onClick={onClose} className="text-xs font-mono text-ork-muted hover:text-ork-text">
            Close
          </button>
        </div>

        {error && (
          <div className="m-4 p-3 border border-ork-red/30 rounded text-xs font-mono text-ork-red">{error}</div>
        )}

        {step === "intent" && (
          <div className="p-4 space-y-4">
            <div className="space-y-2">
              <p className="data-label">Describe the agent you want</p>
              <textarea
                rows={5}
                value={request.intent}
                onChange={(e) => setRequest((prev) => ({ ...prev, intent: e.target.value }))}
                placeholder="Je veux un agent qui trouve toutes les infos légales sur une entreprise française..."
                className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
              />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input
                value={request.use_case || ""}
                onChange={(e) => setRequest((prev) => ({ ...prev, use_case: e.target.value }))}
                placeholder="use case"
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
              />
              <input
                value={request.target_workflow || ""}
                onChange={(e) => setRequest((prev) => ({ ...prev, target_workflow: e.target.value }))}
                placeholder="target workflow"
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
              />
              <input
                value={request.criticality_target || ""}
                onChange={(e) => setRequest((prev) => ({ ...prev, criticality_target: e.target.value }))}
                placeholder="criticality target"
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
              />
              <select
                value={request.preferred_family || ""}
                onChange={(e) => setRequest((prev) => ({ ...prev, preferred_family: e.target.value || undefined }))}
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
              >
                <option value="">family (optional)</option>
                {families.map((family) => (
                  <option key={family.id} value={family.id}>
                    {family.label} ({family.id})
                  </option>
                ))}
              </select>
              <input
                value={request.preferred_output_style || ""}
                onChange={(e) => setRequest((prev) => ({ ...prev, preferred_output_style: e.target.value }))}
                placeholder="preferred output style"
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
              />
              <input
                value={request.preferred_mcp_scope || ""}
                onChange={(e) => setRequest((prev) => ({ ...prev, preferred_mcp_scope: e.target.value }))}
                placeholder="preferred MCP scope"
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
              />
              <input
                value={request.owner || ""}
                onChange={(e) => setRequest((prev) => ({ ...prev, owner: e.target.value }))}
                placeholder="owner"
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm md:col-span-1"
              />
              <select
                multiple
                value={request.preferred_skill_ids || []}
                onChange={(e) => {
                  const selected = Array.from(e.target.selectedOptions).map((opt) => opt.value);
                  setRequest((prev) => ({ ...prev, preferred_skill_ids: selected }));
                }}
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm md:col-span-2 min-h-28"
              >
                {skills.map((skill) => (
                  <option key={skill.skill_id} value={skill.skill_id}>
                    {skill.label} ({skill.skill_id})
                  </option>
                ))}
              </select>
              <input
                value={request.constraints || ""}
                onChange={(e) => setRequest((prev) => ({ ...prev, constraints: e.target.value }))}
                placeholder="constraints / forbidden actions"
                className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm md:col-span-2"
              />
            </div>
            <div className="text-xs font-mono text-ork-dim">
              <div>Family: optional, helps focus the draft on a specific agent type.</div>
              <div>Skills: optional, suggest skills to assign; generation may add or adjust them.</div>
            </div>
            <div className="flex justify-end">
              <button
                onClick={runGeneration}
                disabled={!request.intent || request.intent.trim().length < 10}
                className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 disabled:opacity-40"
              >
                Generate draft
              </button>
            </div>
          </div>
        )}

        {step === "generating" && (
          <div className="p-10 text-center text-sm font-mono text-ork-cyan">Building your agent draft...</div>
        )}

        {step === "review" && draft && (
          <div className="p-4 space-y-4">
            <div className="flex items-center gap-2 text-xs font-mono text-ork-dim">
              <span>Generator:</span>
              <span className="text-ork-cyan">{sourceLabel(source)}</span>
              <StatusBadge status={draft.status} />
            </div>

            <section className="glass-panel p-4 space-y-3">
              <h3 className="section-title text-sm">Review Draft</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <input value={draft.agent_id} onChange={(e) => updateDraft({ agent_id: e.target.value })} className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono" />
                <input value={draft.name} onChange={(e) => updateDraft({ name: e.target.value })} className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm" />
                <input value={draft.family_id} onChange={(e) => updateDraft({ family_id: e.target.value })} placeholder="family_id" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono" />
                <input value={draft.purpose} onChange={(e) => updateDraft({ purpose: e.target.value })} className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm md:col-span-3" />
                <textarea value={draft.description} onChange={(e) => updateDraft({ description: e.target.value })} rows={3} className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm md:col-span-3" />
                <input value={skillIdsCsv} onChange={(e) => setSkillIdsCsv(e.target.value)} placeholder="skill_ids csv" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono md:col-span-3" />
                <input value={routingKeywordsCsv} onChange={(e) => setRoutingKeywordsCsv(e.target.value)} placeholder="selection_hints.routing_keywords" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono md:col-span-2" />
                <input value={workflowIdsCsv} onChange={(e) => setWorkflowIdsCsv(e.target.value)} placeholder="selection_hints.workflow_ids" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono" />
              </div>
            </section>

            <section className="glass-panel p-4 space-y-3">
              <h3 className="section-title text-sm">MCP Selection</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-56 overflow-y-auto border border-ork-border rounded p-2">
                {availableMcps.map((mcp) => {
                  const checked = draft.allowed_mcps.includes(mcp.id);
                  return (
                    <label key={mcp.id} className="flex items-start gap-2 text-xs font-mono">
                      <input type="checkbox" checked={checked} onChange={() => toggleMcp(mcp.id)} />
                      <span>
                        <span className="text-ork-text">{mcp.name}</span>
                        <span className="text-ork-dim"> ({mcp.id})</span>
                        <span className="ml-2 text-ork-dim">{mcp.effect_type}</span>
                        <span className="ml-2 text-ork-dim">{mcp.criticality}</span>
                        {draft.mcp_rationale[mcp.id] && (
                          <span className="ml-2 text-ork-cyan/80">— {draft.mcp_rationale[mcp.id]}</span>
                        )}
                        <span className="ml-2">
                          <StatusBadge status={mcp.orkestra_state} />
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
              <div className="text-xs font-mono text-ork-dim">
                Proposed rationale:
                {draft.allowed_mcps.map((id) => (
                  <div key={id}>
                    <span className="text-ork-cyan">{id}</span>: {draft.mcp_rationale[id] || "selected"}
                  </div>
                ))}
              </div>
              <div>
                <p className="data-label">Suggested missing MCPs</p>
                {draft.suggested_missing_mcps.length === 0 ? (
                  <p className="text-xs font-mono text-ork-dim">none</p>
                ) : (
                  <div className="flex flex-wrap gap-2 mt-1">
                    {draft.suggested_missing_mcps.map((mcp) => (
                      <span key={mcp} className="px-2 py-1 text-xs font-mono border border-ork-amber/30 rounded text-ork-amber">
                        {mcp}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </section>

            <section className="glass-panel p-4 space-y-3">
              <h3 className="section-title text-sm">Governance and Content</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <input value={draft.criticality} onChange={(e) => updateDraft({ criticality: e.target.value })} placeholder="criticality" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono" />
                <input value={draft.cost_profile} onChange={(e) => updateDraft({ cost_profile: e.target.value })} placeholder="cost_profile" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono" />
                <input value={draft.owner || ""} onChange={(e) => updateDraft({ owner: e.target.value || null })} placeholder="owner" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono" />
                <input value={forbiddenEffectsCsv} onChange={(e) => setForbiddenEffectsCsv(e.target.value)} placeholder="forbidden_effects csv" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono md:col-span-3" />
                <input value={limitationsCsv} onChange={(e) => setLimitationsCsv(e.target.value)} placeholder="limitations csv" className="bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono md:col-span-3" />
              </div>
              <div>
                <p className="data-label">prompt_content</p>
                <textarea value={draft.prompt_content} onChange={(e) => updateDraft({ prompt_content: e.target.value })} rows={7} className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono" />
              </div>
              <div>
                <p className="data-label">skills_content</p>
                <textarea value={draft.skills_content} onChange={(e) => updateDraft({ skills_content: e.target.value })} rows={5} className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono" />
              </div>
            </section>

            <div className="flex flex-wrap justify-end gap-2">
              <button
                onClick={runGeneration}
                className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-purple/30 text-ork-purple bg-ork-purple/10"
              >
                Regenerate
              </button>
              <button
                onClick={onClose}
                className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-border text-ork-muted"
              >
                Cancel
              </button>
              <button
                onClick={saveDraft}
                disabled={saving}
                className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 disabled:opacity-40"
              >
                {saving ? "Saving..." : "Save as draft"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
