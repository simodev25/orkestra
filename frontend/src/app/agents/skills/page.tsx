"use client";

import { useEffect, useState } from "react";
import { SkillFormModal } from "@/components/agents/skill-form-modal";
import { ConfirmDangerDialog } from "@/components/ui/confirm-danger-dialog";
import { StatusBadge } from "@/components/ui/status-badge";
import { archiveSkill, getSkillHistory, listSkillsWithAgents, restoreSkill } from "@/lib/families/service";
import type { SkillWithAgents } from "@/lib/families/types";

export default function SkillsAdminPage() {
  const [skills, setSkills] = useState<SkillWithAgents[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingSkill, setEditingSkill] = useState<SkillWithAgents | undefined>(undefined);
  const [pendingArchive, setPendingArchive] = useState<SkillWithAgents | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [archiveError, setArchiveError] = useState<string | null>(null);
  const [showArchived, setShowArchived] = useState(false);
  const [historySkill, setHistorySkill] = useState<SkillWithAgents | null>(null);
  const [historyData, setHistoryData] = useState<any[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  async function load(includeArchived: boolean) {
    setLoading(true);
    setError(null);
    try {
      const data = await listSkillsWithAgents(includeArchived);
      setSkills(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load skills");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(showArchived);
  }, [showArchived]);

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
    void load(showArchived);
  }

  async function openHistory(skill: SkillWithAgents) {
    setHistorySkill(skill);
    setHistoryLoading(true);
    try {
      const data = await getSkillHistory(skill.skill_id);
      setHistoryData(data);
    } catch {
      setHistoryData([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function confirmArchive() {
    if (!pendingArchive) return;
    setArchiving(true);
    setArchiveError(null);
    try {
      const updated = await archiveSkill(pendingArchive.skill_id);
      setSkills((prev) =>
        showArchived
          ? prev.map((s) => (s.skill_id === updated.skill_id ? { ...s, ...updated } : s))
          : prev.filter((s) => s.skill_id !== pendingArchive.skill_id),
      );
      setPendingArchive(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to archive skill";
      setArchiveError(msg);
      setPendingArchive(null);
    } finally {
      setArchiving(false);
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
            Create Skill
          </button>
        </div>
      </div>

      {archiveError && (
        <div className="glass-panel p-3 border border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{archiveError}</p>
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
                <th className="p-3 text-left">version</th>
                <th className="p-3 text-left">status</th>
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
                  <td className="p-3 text-ork-muted">{skill.version || "-"}</td>
                  <td className="p-3">
                    <StatusBadge status={skill.status ?? "active"} />
                  </td>
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
                      onClick={() => void openHistory(skill)}
                      className="text-ork-cyan hover:underline"
                    >
                      History
                    </button>
                    {skill.status !== "archived" && (
                      <button
                        onClick={() => setPendingArchive(skill)}
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

      <SkillFormModal
        key={editingSkill?.skill_id ?? "__create__"}
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={handleSaved}
        initial={editingSkill}
      />

      <ConfirmDangerDialog
        open={Boolean(pendingArchive)}
        title="Archive Skill"
        description="Archiving a skill will mark it as inactive. Agents that reference it will not be affected, but this skill will be hidden by default."
        targetLabel={pendingArchive ? `${pendingArchive.label} (${pendingArchive.skill_id})` : undefined}
        confirmLabel="Archive Skill"
        loading={archiving}
        onCancel={() => {
          if (archiving) return;
          setPendingArchive(null);
        }}
        onConfirm={() => void confirmArchive()}
      />

      {historySkill && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="glass-panel w-full max-w-2xl max-h-[80vh] overflow-y-auto p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-mono font-semibold text-ork-text">
                Version History — {historySkill.label}
              </h2>
              <button
                onClick={() => setHistorySkill(null)}
                className="text-xs font-mono text-ork-dim hover:text-ork-text"
              >
                Close
              </button>
            </div>
            {historyLoading ? (
              <p className="text-xs font-mono text-ork-cyan">Loading history...</p>
            ) : historyData.length === 0 ? (
              <p className="text-xs font-mono text-ork-dim">No history yet. History is recorded on each update.</p>
            ) : (
              <table className="w-full text-xs font-mono">
                <thead className="border-b border-ork-border/60 text-ork-dim">
                  <tr>
                    <th className="p-2 text-left">version</th>
                    <th className="p-2 text-left">label</th>
                    <th className="p-2 text-left">category</th>
                    <th className="p-2 text-left">status</th>
                    <th className="p-2 text-left">replaced_at</th>
                    <th className="p-2 text-left">action</th>
                  </tr>
                </thead>
                <tbody>
                  {historyData.map((h) => (
                    <tr key={h.id} className="border-b border-ork-border/30">
                      <td className="p-2 text-ork-cyan">{h.version}</td>
                      <td className="p-2 text-ork-text">{h.label}</td>
                      <td className="p-2 text-ork-muted">{h.category}</td>
                      <td className="p-2 text-ork-muted">{h.status}</td>
                      <td className="p-2 text-ork-dim">{new Date(h.replaced_at).toLocaleString()}</td>
                      <td className="p-2">
                        <button
                          onClick={async () => {
                            await restoreSkill(historySkill.skill_id, h.id);
                            setHistorySkill(null);
                            void load(showArchived);
                          }}
                          className="text-ork-cyan hover:underline text-[10px]"
                        >
                          Restore
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
