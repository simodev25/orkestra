"use client";

import { useEffect, useState } from "react";
import type { SkillDefinition, SkillCreatePayload, SkillUpdatePayload } from "@/lib/families/types";
import { createSkill, updateSkill } from "@/lib/families/service";
import { listFamilies } from "@/lib/families/service";
import type { FamilyDefinition } from "@/lib/families/types";

interface SkillFormModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: (skill: SkillDefinition) => void;
  initial?: SkillDefinition;
}

export function SkillFormModal({ open, onClose, onSaved, initial }: SkillFormModalProps) {
  const isEdit = Boolean(initial);

  const [skillId, setSkillId] = useState(initial?.skill_id ?? "");
  const [label, setLabel] = useState(initial?.label ?? "");
  const [category, setCategory] = useState(initial?.category ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [behaviorTemplates, setBehaviorTemplates] = useState(
    (initial?.behavior_templates ?? []).join("\n"),
  );
  const [outputGuidelines, setOutputGuidelines] = useState(
    (initial?.output_guidelines ?? []).join("\n"),
  );
  const [allowedFamilies, setAllowedFamilies] = useState<string[]>(initial?.allowed_families ?? []);
  const [owner, setOwner] = useState(initial?.owner ?? "");
  const [families, setFamilies] = useState<FamilyDefinition[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    listFamilies()
      .then(setFamilies)
      .catch(() => setFamilies([]));
  }, [open]);

  if (!open) return null;

  function toggleFamily(familyId: string) {
    setAllowedFamilies((prev) =>
      prev.includes(familyId) ? prev.filter((id) => id !== familyId) : [...prev, familyId],
    );
  }

  function parseLines(text: string): string[] {
    return text
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
  }

  function validate(): string[] {
    const issues: string[] = [];
    if (!isEdit && !skillId.trim()) issues.push("skill_id is required");
    if (!label.trim()) issues.push("label is required");
    if (!category.trim()) issues.push("category is required");
    return issues;
  }

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const issues = validate();
    if (issues.length > 0) {
      setError(issues.join(" | "));
      return;
    }
    setError(null);
    setSaving(true);
    try {
      let saved: SkillDefinition;
      if (isEdit && initial) {
        const payload: SkillUpdatePayload = {
          label: label.trim(),
          category: category.trim(),
          description: description.trim() || undefined,
          behavior_templates: parseLines(behaviorTemplates),
          output_guidelines: parseLines(outputGuidelines),
          allowed_families: allowedFamilies,
          owner: owner.trim() || undefined,
        };
        saved = await updateSkill(initial.skill_id, payload);
      } else {
        const payload: SkillCreatePayload = {
          skill_id: skillId.trim(),
          label: label.trim(),
          category: category.trim(),
          description: description.trim() || undefined,
          behavior_templates: parseLines(behaviorTemplates),
          output_guidelines: parseLines(outputGuidelines),
          allowed_families: allowedFamilies,
          owner: owner.trim() || undefined,
        };
        saved = await createSkill(payload);
      }
      onSaved(saved);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save skill");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-xl glass-panel border border-ork-border my-auto">
        <div className="p-4 border-b border-ork-border flex items-center justify-between">
          <h2 className="text-sm font-semibold">{isEdit ? "Edit Skill" : "Create Skill"}</h2>
          <button
            onClick={onClose}
            disabled={saving}
            className="text-xs font-mono text-ork-muted hover:text-ork-text disabled:opacity-50"
          >
            Cancel
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {error && (
            <div className="p-2 border border-ork-red/30 rounded text-xs font-mono text-ork-red">{error}</div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <p className="data-label">skill_id</p>
              <input
                value={skillId}
                onChange={(e) => setSkillId(e.target.value)}
                placeholder="data_retrieval"
                disabled={isEdit}
                className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono disabled:opacity-60"
              />
            </div>
            <div>
              <p className="data-label">label</p>
              <input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Data Retrieval"
                className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
              />
            </div>
            <div>
              <p className="data-label">category</p>
              <input
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="retrieval"
                className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
              />
            </div>
            {isEdit && initial?.version && (
              <div>
                <p className="data-label">version (auto-managed)</p>
                <p className="px-3 py-2 text-sm font-mono text-ork-cyan bg-ork-bg border border-ork-border rounded opacity-70">
                  {initial.version} → next on save
                </p>
              </div>
            )}
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

          <div>
            <p className="data-label">description</p>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              placeholder="Optional description..."
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
            />
          </div>

          <div>
            <p className="data-label">behavior_templates (one per line)</p>
            <textarea
              value={behaviorTemplates}
              onChange={(e) => setBehaviorTemplates(e.target.value)}
              rows={4}
              placeholder="Always cite your sources&#10;Return structured JSON when possible"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <p className="data-label">output_guidelines (one per line)</p>
            <textarea
              value={outputGuidelines}
              onChange={(e) => setOutputGuidelines(e.target.value)}
              rows={4}
              placeholder="Include confidence score&#10;Provide source URL"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <p className="data-label">allowed_families</p>
            {families.length === 0 ? (
              <p className="text-xs font-mono text-ork-dim">No families available.</p>
            ) : (
              <div className="grid grid-cols-2 gap-1.5 border border-ork-border rounded p-2 max-h-40 overflow-y-auto">
                {families.map((f) => (
                  <label key={f.id} className="flex items-center gap-2 text-xs font-mono">
                    <input
                      type="checkbox"
                      checked={allowedFamilies.includes(f.id)}
                      onChange={() => toggleFamily(f.id)}
                    />
                    <span>
                      <span className="text-ork-text">{f.label}</span>
                      <span className="text-ork-dim"> ({f.id})</span>
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onClose}
              disabled={saving}
              className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-border text-ork-muted disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={saving}
              className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 disabled:opacity-50"
            >
              {saving ? "Saving..." : isEdit ? "Save Changes" : "Create Skill"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
