"use client";

import { useEffect, useState } from "react";
import { SkillFormModal } from "@/components/agents/skill-form-modal";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";
import { deleteSkill, listSkillsWithAgents } from "@/lib/families/service";
import type { SkillWithAgents } from "@/lib/families/types";

export default function SkillsAdminPage() {
  const [skills, setSkills] = useState<SkillWithAgents[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingSkill, setEditingSkill] = useState<SkillWithAgents | undefined>(undefined);
  const [pendingDelete, setPendingDelete] = useState<SkillWithAgents | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await listSkillsWithAgents();
      setSkills(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load skills");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function openCreate() {
    setEditingSkill(undefined);
    setModalOpen(true);
  }

  function openEdit(skill: SkillWithAgents) {
    setEditingSkill(skill);
    setModalOpen(true);
  }

  function handleSaved() {
    setModalOpen(false);
    void load();
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteSkill(pendingDelete.skill_id);
      setSkills((prev) => prev.filter((s) => s.skill_id !== pendingDelete.skill_id));
      setPendingDelete(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete skill";
      // 409 conflict — skill is in use
      setDeleteError(msg);
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5 animate-fade-in">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-ork-text tracking-wide">Agent Skills</h1>
          <p className="text-xs text-ork-dim font-mono mt-1">
            Manage skill definitions. Skills define capabilities available to agent families.
          </p>
        </div>
        <button
          onClick={openCreate}
          className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10"
        >
          Create Skill
        </button>
      </div>

      {deleteError && (
        <div className="glass-panel p-3 border border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{deleteError}</p>
        </div>
      )}

      {loading ? (
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">Loading skills...</div>
      ) : error ? (
        <div className="glass-panel p-6 text-sm font-mono text-ork-red">{error}</div>
      ) : skills.length === 0 ? (
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-dim">
          No skills defined yet. Create the first one.
        </div>
      ) : (
        <div className="glass-panel overflow-x-auto">
          <table className="w-full text-xs font-mono">
            <thead className="border-b border-ork-border/60 text-ork-dim bg-ork-panel/60">
              <tr>
                <th className="p-3 text-left">skill_id</th>
                <th className="p-3 text-left">label</th>
                <th className="p-3 text-left">category</th>
                <th className="p-3 text-left">allowed_families</th>
                <th className="p-3 text-left">agents</th>
                <th className="p-3 text-left">actions</th>
              </tr>
            </thead>
            <tbody>
              {skills.map((skill) => (
                <tr key={skill.skill_id} className="border-b border-ork-border/40 align-top">
                  <td className="p-3 text-ork-cyan">{skill.skill_id}</td>
                  <td className="p-3 text-ork-text font-semibold">{skill.label}</td>
                  <td className="p-3 text-ork-muted">{skill.category}</td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1">
                      {skill.allowed_families.length > 0 ? (
                        skill.allowed_families.map((fid) => (
                          <span
                            key={fid}
                            className="px-1.5 py-0.5 text-[10px] font-mono rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10"
                          >
                            {fid}
                          </span>
                        ))
                      ) : (
                        <span className="text-ork-dim">all</span>
                      )}
                    </div>
                  </td>
                  <td className="p-3 text-ork-dim">{skill.agents.length}</td>
                  <td className="p-3 space-x-3">
                    <button
                      onClick={() => openEdit(skill)}
                      className="text-ork-purple hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => setPendingDelete(skill)}
                      className="text-ork-red hover:underline"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <SkillFormModal
        key={editingSkill?.skill_id ?? "__create__"}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
        initial={editingSkill}
      />

      <ConfirmDangerDialog
        open={Boolean(pendingDelete)}
        title="Delete Skill"
        description="Deleting a skill will remove it from agents that reference it. This action cannot be undone."
        targetLabel={pendingDelete ? `${pendingDelete.label} (${pendingDelete.skill_id})` : undefined}
        confirmLabel="Delete Skill"
        loading={deleting}
        onCancel={() => {
          if (deleting) return;
          setPendingDelete(null);
        }}
        onConfirm={() => void confirmDelete()}
      />
    </div>
  );
}
