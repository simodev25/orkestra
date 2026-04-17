"use client";

import { useState } from "react";
import { RotateCcw, Save } from "lucide-react";
import type { GeneratedAgentDraft } from "@/lib/agent-registry/types";

type Tab = "prompt" | "skills" | "config";

interface OrchestratorResultPanelProps {
  draft: GeneratedAgentDraft;
  selectedAgentIds: string[];
  onModify: () => void;
  onRegenerate: () => void;
  onSave: () => Promise<void>;
  saving: boolean;
}

export default function OrchestratorResultPanel({
  draft,
  selectedAgentIds,
  onModify,
  onRegenerate,
  onSave,
  saving,
}: OrchestratorResultPanelProps) {
  const [tab, setTab] = useState<Tab>("prompt");

  const configJson = JSON.stringify(
    {
      id: draft.agent_id,
      name: draft.name,
      family_id: draft.family_id,
      agent_ids: selectedAgentIds,
      mode: "sequential",
      criticality: draft.criticality,
      cost_profile: draft.cost_profile,
    },
    null,
    2,
  );

  const tabs: { key: Tab; label: string }[] = [
    { key: "prompt", label: "Prompt" },
    { key: "skills", label: "Skills" },
    { key: "config", label: "Config" },
  ];

  return (
    <div className="flex flex-col flex-1 overflow-hidden">
      {/* Tab bar + actions */}
      <div className="flex items-center border-b border-[#1e2530] bg-[#111827] px-4">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`text-xs px-4 py-3 border-b-2 font-mono transition-colors -mb-px ${
              tab === t.key
                ? "border-ork-cyan text-ork-cyan"
                : "border-transparent text-ork-dim hover:text-ork-text"
            }`}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={onModify}
            className="text-xs px-3 py-1.5 bg-[#1e2530] text-ork-text rounded hover:bg-[#2d3748] transition-colors"
          >
            ✎ Modifier
          </button>
          <button
            onClick={onRegenerate}
            className="text-xs px-3 py-1.5 bg-[#1e2530] text-ork-text rounded hover:bg-[#2d3748] transition-colors flex items-center gap-1"
          >
            <RotateCcw className="w-3 h-3" />
            Regénérer
          </button>
          <button
            onClick={onSave}
            disabled={saving}
            className="text-xs px-4 py-1.5 bg-ork-cyan text-black font-bold rounded hover:bg-ork-cyan/90 transition-colors flex items-center gap-1 disabled:opacity-50"
          >
            <Save className="w-3 h-3" />
            {saving ? "Sauvegarde…" : "Sauvegarder"}
          </button>
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-5">
        {tab === "prompt" && (
          <div>
            <div className="text-[10px] text-ork-dim uppercase tracking-widest mb-3">
              Prompt généré
            </div>
            <pre className="bg-[#111827] border border-[#1e2530] rounded-lg p-4 text-xs text-[#a0c4ce] font-mono leading-relaxed whitespace-pre-wrap">
              {draft.prompt_content}
            </pre>
          </div>
        )}

        {tab === "skills" && (
          <div>
            <div className="text-[10px] text-ork-dim uppercase tracking-widest mb-3">
              Skills générées
            </div>
            <div className="flex flex-col gap-3">
              {draft.skill_ids.map((skillId) => {
                // Extract description from skills_content (format: "skill_name: description")
                const match = new RegExp(
                  `${skillId}:\\s*([^\\n]+)`,
                  "i",
                ).exec(draft.skills_content ?? "");
                const desc = match ? match[1].trim() : "";
                return (
                  <div
                    key={skillId}
                    className="bg-[#111827] border border-[#1e2530] rounded-lg px-4 py-3"
                  >
                    <div className="text-xs text-ork-cyan font-mono font-semibold mb-1">
                      {skillId}
                    </div>
                    {desc && (
                      <div className="text-xs text-ork-dim leading-relaxed">{desc}</div>
                    )}
                  </div>
                );
              })}
              {draft.limitations.length > 0 && (
                <div className="mt-2">
                  <div className="text-[10px] text-ork-dim uppercase tracking-widest mb-2">
                    Limitations
                  </div>
                  <ul className="list-disc list-inside text-xs text-ork-dim space-y-1">
                    {draft.limitations.map((l, i) => (
                      <li key={i}>{l}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        )}

        {tab === "config" && (
          <div>
            <div className="text-[10px] text-ork-dim uppercase tracking-widest mb-3">
              Configuration JSON
            </div>
            <pre className="bg-[#111827] border border-[#1e2530] rounded-lg p-4 text-xs text-[#a0c4ce] font-mono leading-relaxed">
              {configJson}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
