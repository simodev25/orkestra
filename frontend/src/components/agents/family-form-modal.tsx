"use client";

import { useState } from "react";
import type { FamilyDefinition, FamilyCreatePayload, FamilyUpdatePayload } from "@/lib/families/types";
import { createFamily, updateFamily } from "@/lib/families/service";

interface FamilyFormModalProps {
  open: boolean;
  onClose: () => void;
  onSaved: (family: FamilyDefinition) => void;
  initial?: FamilyDefinition;
}

function parseLines(text: string): string[] {
  return text
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
}

function toLines(arr: string[] | undefined | null): string {
  if (!arr || arr.length === 0) return "";
  return arr.join("\n");
}

export function FamilyFormModal({ open, onClose, onSaved, initial }: FamilyFormModalProps) {
  const isEdit = Boolean(initial);

  const [id, setId] = useState(initial?.id ?? "");
  const [label, setLabel] = useState(initial?.label ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [defaultSystemRules, setDefaultSystemRules] = useState(toLines(initial?.default_system_rules));
  const [defaultForbiddenEffects, setDefaultForbiddenEffects] = useState(toLines(initial?.default_forbidden_effects));
  const [defaultOutputExpectations, setDefaultOutputExpectations] = useState(
    toLines(initial?.default_output_expectations),
  );
  const [owner, setOwner] = useState(initial?.owner ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  function validate(): string[] {
    const issues: string[] = [];
    if (!isEdit && !/^[a-z0-9_-]+$/.test(id.trim())) {
      issues.push("id must match ^[a-z0-9_-]+$");
    }
    if (!label.trim()) issues.push("label is required");
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
      let saved: FamilyDefinition;
      if (isEdit && initial) {
        const payload: FamilyUpdatePayload = {
          label: label.trim(),
          description: description.trim() || undefined,
          default_system_rules: parseLines(defaultSystemRules),
          default_forbidden_effects: parseLines(defaultForbiddenEffects),
          default_output_expectations: parseLines(defaultOutputExpectations),
          owner: owner.trim() || undefined,
        };
        saved = await updateFamily(initial.id, payload);
      } else {
        const payload: FamilyCreatePayload = {
          id: id.trim(),
          label: label.trim(),
          description: description.trim() || undefined,
          default_system_rules: parseLines(defaultSystemRules),
          default_forbidden_effects: parseLines(defaultForbiddenEffects),
          default_output_expectations: parseLines(defaultOutputExpectations),
          owner: owner.trim() || undefined,
        };
        saved = await createFamily(payload);
      }
      onSaved(saved);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to save family");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label={isEdit ? "Edit Family" : "Create Family"} className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-center justify-center p-4 overflow-y-auto">
      <div className="w-full max-w-lg glass-panel border border-ork-border my-auto">
        <div className="p-4 border-b border-ork-border flex items-center justify-between">
          <h2 className="text-sm font-semibold">{isEdit ? "Edit Family" : "Create Family"}</h2>
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

          <div>
            <p className="data-label">id</p>
            <input
              value={id}
              onChange={(e) => setId(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "_"))}
              placeholder="analyst"
              disabled={isEdit}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono disabled:opacity-60"
            />
            {!isEdit && (
              <p className="text-[10px] font-mono text-ork-dim mt-1">lowercase letters, digits, _ and - only</p>
            )}
          </div>

          <div>
            <p className="data-label">label</p>
            <input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="Analyst"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
            />
          </div>

          <div>
            <p className="data-label">description</p>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Optional description of this agent family..."
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
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
            <p className="data-label">default_system_rules (one per line)</p>
            <textarea
              value={defaultSystemRules}
              onChange={(e) => setDefaultSystemRules(e.target.value)}
              rows={4}
              placeholder="Always verify data sources&#10;Never expose PII in outputs"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <p className="data-label">default_forbidden_effects (one per line)</p>
            <textarea
              value={defaultForbiddenEffects}
              onChange={(e) => setDefaultForbiddenEffects(e.target.value)}
              rows={3}
              placeholder="write&#10;act"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
          </div>

          <div>
            <p className="data-label">default_output_expectations (one per line)</p>
            <textarea
              value={defaultOutputExpectations}
              onChange={(e) => setDefaultOutputExpectations(e.target.value)}
              rows={3}
              placeholder="Return structured JSON&#10;Include confidence score"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono"
            />
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
              {saving ? "Saving..." : isEdit ? "Save Changes" : "Create Family"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
