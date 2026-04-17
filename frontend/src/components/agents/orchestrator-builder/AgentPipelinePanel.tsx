"use client";

import { useState, useRef } from "react";
import { GripVertical, X, Plus } from "lucide-react";
import type { AgentDefinition } from "@/lib/agent-registry/types";

export type SelectionMode = "manual" | "auto";

interface AgentPipelinePanelProps {
  mode: SelectionMode;
  onModeChange: (mode: SelectionMode) => void;
  /** Manual mode: ordered list of selected agent IDs */
  selectedIds: string[];
  onSelectedIdsChange: (ids: string[]) => void;
  /** Auto mode: free-text description */
  useCase: string;
  onUseCaseChange: (text: string) => void;
  /** Full registry for the add-agent picker */
  allAgents: AgentDefinition[];
}

export default function AgentPipelinePanel({
  mode,
  onModeChange,
  selectedIds,
  onSelectedIdsChange,
  useCase,
  onUseCaseChange,
  allAgents,
}: AgentPipelinePanelProps) {
  const [showPicker, setShowPicker] = useState(false);
  const dragIdx = useRef<number | null>(null);

  // ── Drag & drop ──────────────────────────────────────────────────────
  function handleDragStart(idx: number) {
    dragIdx.current = idx;
  }

  function handleDrop(targetIdx: number) {
    const from = dragIdx.current;
    if (from === null || from === targetIdx) return;
    const next = [...selectedIds];
    const [moved] = next.splice(from, 1);
    next.splice(targetIdx, 0, moved);
    onSelectedIdsChange(next);
    dragIdx.current = null;
  }

  function removeAgent(id: string) {
    onSelectedIdsChange(selectedIds.filter((x) => x !== id));
  }

  function addAgent(id: string) {
    if (!selectedIds.includes(id)) {
      onSelectedIdsChange([...selectedIds, id]);
    }
    setShowPicker(false);
  }

  // Agents not yet in the pipeline
  const available = allAgents.filter((a) => !selectedIds.includes(a.id));

  // Lookup map for display
  const agentMap = Object.fromEntries(allAgents.map((a) => [a.id, a]));

  return (
    <div className="flex flex-col h-full bg-[#111827] border-r border-[#1e2530]">

      {/* Mode toggle bar */}
      <div className="px-4 py-3 border-b border-[#1e2530] flex items-center gap-3">
        <span className="text-xs text-ork-dim">Mode :</span>
        <div className="flex bg-[#0d1117] border border-[#2d3748] rounded-full p-0.5">
          {(["manual", "auto"] as const).map((m) => (
            <button
              key={m}
              onClick={() => onModeChange(m)}
              className={`text-xs px-4 py-1.5 rounded-full transition-colors font-mono ${
                mode === m
                  ? "bg-ork-cyan text-black font-bold"
                  : "text-ork-dim hover:text-ork-text"
              }`}
            >
              {m === "manual" ? "Manuel" : "Auto (LLM choisit)"}
            </button>
          ))}
        </div>
      </div>

      {/* Manual mode — drag & drop list */}
      {mode === "manual" && (
        <div className="flex flex-col flex-1 overflow-hidden">
          <div className="px-4 pt-3 pb-1 text-[10px] text-ork-dim uppercase tracking-widest">
            Pipeline d&apos;agents — glisser pour ordonner
          </div>
          <div className="flex-1 overflow-y-auto px-3 py-2 flex flex-col gap-2">
            {selectedIds.map((id, idx) => {
              const agent = agentMap[id];
              return (
                <div
                  key={id}
                  draggable
                  onDragStart={() => handleDragStart(idx)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleDrop(idx)}
                  className="flex items-center gap-2 bg-[#1e2530] border border-ork-cyan rounded-md px-3 py-2 cursor-grab active:cursor-grabbing"
                >
                  <GripVertical className="w-4 h-4 text-[#2d3748] shrink-0" />
                  <span className="bg-ork-cyan text-black text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0">
                    {idx + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-ork-cyan font-mono truncate">{id}</div>
                    {agent && (
                      <div className="text-[10px] text-ork-dim truncate">{agent.name}</div>
                    )}
                  </div>
                  <button
                    onClick={() => removeAgent(id)}
                    className="text-ork-dim hover:text-ork-red shrink-0"
                    aria-label={`Remove ${id}`}
                  >
                    <X className="w-3 h-3" />
                  </button>
                </div>
              );
            })}

            {/* Add button */}
            <div className="relative">
              <button
                onClick={() => setShowPicker((v) => !v)}
                className="w-full border border-dashed border-[#2d3748] rounded-md py-2 text-xs text-ork-dim hover:border-ork-cyan hover:text-ork-cyan flex items-center justify-center gap-1.5 transition-colors"
              >
                <Plus className="w-3 h-3" />
                Ajouter un agent…
              </button>

              {showPicker && (
                <div className="absolute left-0 right-0 top-full mt-1 z-20 bg-[#1e2530] border border-[#2d3748] rounded-md shadow-lg max-h-48 overflow-y-auto">
                  {available.length === 0 ? (
                    <div className="px-3 py-2 text-xs text-ork-dim">Tous les agents sont déjà sélectionnés</div>
                  ) : (
                    available.map((a) => (
                      <button
                        key={a.id}
                        onClick={() => addAgent(a.id)}
                        className="w-full text-left px-3 py-2 text-xs text-ork-text hover:bg-ork-cyan/10 hover:text-ork-cyan border-b border-[#0d1117] last:border-0 font-mono"
                      >
                        {a.id}
                        <span className="ml-2 text-ork-dim font-sans">{a.name}</span>
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Auto mode — textarea */}
      {mode === "auto" && (
        <div className="flex flex-col flex-1 p-4 gap-3">
          <div className="text-[10px] text-ork-dim uppercase tracking-widest">
            Décris ton pipeline
          </div>
          <textarea
            className="flex-1 bg-[#0d1117] border border-[#2d6a7a] rounded-md p-3 text-xs text-[#a0c4ce] font-mono resize-none focus:outline-none focus:border-ork-cyan placeholder:text-[#2d3748]"
            placeholder="Ex: Je veux un pipeline qui gère la recherche hôtelière. Il doit évaluer la météo, vérifier le budget, puis trouver les hôtels disponibles…"
            value={useCase}
            onChange={(e) => onUseCaseChange(e.target.value)}
          />
          <p className="text-[10px] text-ork-dim leading-relaxed">
            Le LLM lira les descriptions de tous les agents disponibles et sélectionnera ceux qui correspondent à ton pipeline.
          </p>
        </div>
      )}
    </div>
  );
}
