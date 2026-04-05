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

export function FamilyFormModal({ open, onClose, onSaved, initial }: FamilyFormModalProps) {
  const isEdit = Boolean(initial);

  const [id, setId] = useState(initial?.id ?? "");
  const [label, setLabel] = useState(initial?.label ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
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
        };
        saved = await updateFamily(initial.id, payload);
      } else {
        const payload: FamilyCreatePayload = {
          id: id.trim(),
          label: label.trim(),
          description: description.trim() || undefined,
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
    <div className="fixed inset-0 z-50 bg-black/55 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="w-full max-w-md glass-panel border border-ork-border">
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
