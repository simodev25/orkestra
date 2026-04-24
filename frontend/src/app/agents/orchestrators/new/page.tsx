"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import AgentPipelinePanel, {
  type SelectionMode,
} from "@/components/agents/orchestrator-builder/AgentPipelinePanel";
import OrchestratorResultPanel from "@/components/agents/orchestrator-builder/OrchestratorResultPanel";
import { listAgents, generateOrchestratorDraft, saveGeneratedDraft } from "@/lib/agent-registry/service";
import type { AgentDefinition, GeneratedAgentDraft } from "@/lib/agent-registry/types";

export default function OrchestratorBuilderPage() {
  const router = useRouter();

  // Registry
  const [allAgents, setAllAgents] = useState<AgentDefinition[]>([]);

  // Left panel state
  const [mode, setMode] = useState<SelectionMode>("manual");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [useCase, setUseCase] = useState("");

  // Right panel — config form
  const [name, setName] = useState("");
  const [userInstructions, setUserInstructions] = useState("");

  // Generation state
  const [generating, setGenerating] = useState(false);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [draft, setDraft] = useState<GeneratedAgentDraft | null>(null);
  const [resultSelectedIds, setResultSelectedIds] = useState<string[]>([]);

  // Save state
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    listAgents({ status: "active" })
      .then((agents) => setAllAgents(agents.filter((a) => a.family_id !== "orchestration")))
      .catch(console.error);
  }, []);

  const canGenerate =
    name.trim().length >= 3 &&
    (mode === "manual" ? selectedIds.length >= 2 : useCase.trim().length > 0);

  async function handleGenerate() {
    setGenerating(true);
    setGenerateError(null);
    try {
      const resp = await generateOrchestratorDraft({
        name: name.trim(),
        agent_ids: mode === "manual" ? selectedIds : [],
        use_case_description: mode === "auto" ? useCase.trim() : undefined,
        user_instructions: userInstructions.trim() || undefined,
        routing_strategy: "sequential",
      });
      setDraft(resp.draft);
      setResultSelectedIds(
        mode === "manual" ? selectedIds : resp.selected_agent_ids,
      );
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Génération échouée");
    } finally {
      setGenerating(false);
    }
  }

  function handleModify() {
    setDraft(null);
    setGenerateError(null);
  }

  async function handleSave() {
    if (!draft) return;
    setSaving(true);
    try {
      const saved = await saveGeneratedDraft(draft);
      router.push(`/agents/${saved.id}`);
    } catch (err) {
      setGenerateError(err instanceof Error ? err.message : "Sauvegarde échouée");
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Page header */}
      <div className="flex items-center gap-4 px-6 py-3.5 border-b border-ork-border shrink-0">
        <button
          onClick={() => router.push("/agents")}
          className="text-xs text-ork-muted hover:text-ork-text transition-colors font-mono"
        >
          ← Agents
        </button>
        <h1 className="text-sm font-bold font-mono text-ork-text">
          Orchestrator Builder
        </h1>
        <span className="text-[10px] text-ork-cyan border border-ork-cyan/40 px-2 py-0.5 rounded font-mono">
          BETA
        </span>
      </div>

      {/* Split layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* LEFT — agent selection */}
        <div className="w-80 shrink-0 flex flex-col overflow-hidden">
          <AgentPipelinePanel
            mode={mode}
            onModeChange={setMode}
            selectedIds={selectedIds}
            onSelectedIdsChange={setSelectedIds}
            useCase={useCase}
            onUseCaseChange={setUseCase}
            allAgents={allAgents}
          />
        </div>

        {/* RIGHT — config + result */}
        <div className="flex flex-col flex-1 overflow-hidden">
          {/* Config form — fades when result shown */}
          <div
            className={`px-6 py-5 border-b border-ork-border flex flex-col gap-4 shrink-0 transition-opacity ${
              draft ? "opacity-50" : "opacity-100"
            }`}
          >
            {/* Name */}
            <div>
              <label className="block text-[10px] text-ork-muted uppercase tracking-widest font-mono mb-1.5">
                Nom de l&apos;orchestrateur
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="hotel_pipeline_orchestrator"
                disabled={!!draft}
                className="field w-full disabled:cursor-not-allowed disabled:opacity-60"
              />
            </div>

            {/* LLM instructions */}
            <div>
              <label className="block text-[10px] text-ork-muted uppercase tracking-widest font-mono mb-1.5">
                Instructions pour le LLM{" "}
                <span className="text-[9px] normal-case tracking-normal text-ork-muted-2">
                  (contexte, priorités, contraintes…)
                </span>
              </label>
              <textarea
                value={userInstructions}
                onChange={(e) => setUserInstructions(e.target.value)}
                placeholder="Ex: Cet orchestrateur gère un pipeline hôtelier. Les agents doivent être appelés dans l'ordre : météo → budget → hôtels…"
                disabled={!!draft}
                rows={3}
                className="field w-full resize-none disabled:cursor-not-allowed disabled:opacity-60"
              />
            </div>

            {/* Generate button */}
            {!draft && (
              <button
                onClick={handleGenerate}
                disabled={!canGenerate || generating}
                className="btn btn--cyan w-full py-2.5 justify-center disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {generating ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    Génération en cours…
                  </>
                ) : (
                  "⚡ Générer l'orchestrateur"
                )}
              </button>
            )}

            {generateError && (
              <div className="text-xs text-ork-red bg-ork-red/10 border border-ork-red/30 rounded px-3 py-2 font-mono">
                {generateError}
              </div>
            )}

            {!canGenerate && !generating && !draft && (
              <p className="text-[10px] text-ork-muted font-mono">
                {mode === "manual"
                  ? "Sélectionne au moins 2 agents et donne un nom (≥ 3 caractères)."
                  : "Décris ton pipeline et donne un nom (≥ 3 caractères)."}
              </p>
            )}
          </div>

          {/* Result panel */}
          {draft && (
            <OrchestratorResultPanel
              draft={draft}
              selectedAgentIds={resultSelectedIds}
              onModify={handleModify}
              onRegenerate={handleGenerate}
              onSave={handleSave}
              saving={saving}
            />
          )}
        </div>
      </div>
    </div>
  );
}
