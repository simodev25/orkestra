"use client";

import { useEffect, useState } from "react";
import { FamilyFormModal } from "@/components/agents/family-form-modal";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";
import { StatusBadge } from "@/components/ui/status-badge";
import { archiveFamily, listFamilies } from "@/lib/families/service";
import type { FamilyDefinition } from "@/lib/families/types";

export default function FamiliesAdminPage() {
  const [families, setFamilies] = useState<FamilyDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingFamily, setEditingFamily] = useState<FamilyDefinition | undefined>(undefined);
  const [pendingArchive, setPendingArchive] = useState<FamilyDefinition | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);

  async function load(includeArchived: boolean) {
    setLoading(true);
    setError(null);
    try {
      const data = await listFamilies(includeArchived);
      setFamilies(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load families");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(showArchived);
  }, [showArchived]);

  function openCreate() {
    setEditingFamily(undefined);
    setModalOpen(true);
  }

  function openEdit(family: FamilyDefinition) {
    setEditingFamily(family);
    setModalOpen(true);
  }

  function handleSaved(family: FamilyDefinition) {
    setModalOpen(false);
    setFamilies((prev) => {
      const idx = prev.findIndex((f) => f.id === family.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = family;
        return next;
      }
      return [...prev, family];
    });
  }

  async function confirmArchive() {
    if (!pendingArchive) return;
    setArchiving(true);
    setArchiveError(null);
    try {
      const updated = await archiveFamily(pendingArchive.id);
      setFamilies((prev) =>
        showArchived
          ? prev.map((f) => (f.id === updated.id ? updated : f))
          : prev.filter((f) => f.id !== updated.id),
      );
      setPendingArchive(null);
    } catch (err: unknown) {
      setArchiveError(err instanceof Error ? err.message : "Failed to archive family");
      setPendingArchive(null);
    } finally {
      setArchiving(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5 animate-fade-in">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ork-text tracking-wide">Agent Families</h1>
          <p className="text-xs text-ork-dim font-mono mt-1">
            Manage agent family definitions. Families group agents by role and scope.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-mono text-ork-muted cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showArchived}
              onChange={(e) => setShowArchived(e.target.checked)}
              className="accent-ork-cyan"
            />
            Show archived
          </label>
          <button
            onClick={openCreate}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10"
          >
            Create Family
          </button>
        </div>
      </div>

      {archiveError && (
        <div className="glass-panel p-3 border border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{archiveError}</p>
        </div>
      )}

      {loading ? (
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">Loading families...</div>
      ) : error ? (
        <div className="glass-panel p-6 text-sm font-mono text-ork-red">{error}</div>
      ) : families.length === 0 ? (
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-dim">
          No families defined yet. Create the first one.
        </div>
      ) : (
        <div className="glass-panel overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead className="border-b border-ork-border/60 text-ork-dim bg-ork-panel/60">
              <tr>
                <th className="p-3 text-left">id</th>
                <th className="p-3 text-left">label</th>
                <th className="p-3 text-left">version</th>
                <th className="p-3 text-left">status</th>
                <th className="p-3 text-left">owner</th>
                <th className="p-3 text-left">description</th>
                <th className="p-3 text-left">created_at</th>
                <th className="p-3 text-left">actions</th>
              </tr>
            </thead>
            <tbody>
              {families.map((family) => (
                <tr key={family.id} className="border-b border-ork-border/40 align-top">
                  <td className="p-3 text-ork-cyan">{family.id}</td>
                  <td className="p-3 text-ork-text font-semibold">{family.label}</td>
                  <td className="p-3 text-ork-muted">{family.version || "-"}</td>
                  <td className="p-3">
                    <StatusBadge status={family.status} />
                  </td>
                  <td className="p-3 text-ork-muted">{family.owner || "-"}</td>
                  <td className="p-3 text-ork-muted max-w-[240px] truncate">{family.description || "-"}</td>
                  <td className="p-3 text-ork-dim">{new Date(family.created_at).toLocaleDateString()}</td>
                  <td className="p-3 space-x-3">
                    <button
                      onClick={() => openEdit(family)}
                      className="text-ork-purple hover:underline"
                    >
                      Edit
                    </button>
                    {family.status !== "archived" && (
                      <button
                        onClick={() => setPendingArchive(family)}
                        className="text-ork-amber hover:underline"
                      >
                        Archive
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <FamilyFormModal
        key={editingFamily?.id ?? "__create__"}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
        initial={editingFamily}
      />

      <ConfirmDangerDialog
        open={Boolean(pendingArchive)}
        title="Archive Family"
        description="Archiving a family will mark it as inactive. Agents that reference it will not be affected, but this family will be hidden by default. This action can be reviewed later."
        targetLabel={pendingArchive ? `${pendingArchive.label} (${pendingArchive.id})` : undefined}
        confirmLabel="Archive Family"
        loading={archiving}
        onCancel={() => {
          if (archiving) return;
          setPendingArchive(null);
        }}
        onConfirm={() => void confirmArchive()}
      />
    </div>
  );
}
