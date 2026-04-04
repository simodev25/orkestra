"use client";

import { useState, useEffect, useCallback } from "react";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { Workflow } from "@/lib/types";

export default function WorkflowsPage() {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [publishing, setPublishing] = useState<string | null>(null);

  const [formName, setFormName] = useState("");
  const [formUseCase, setFormUseCase] = useState("");
  const [formExecMode, setFormExecMode] = useState("sequential");

  const loadWorkflows = useCallback(async () => {
    try {
      const data = await api.listWorkflows();
      setWorkflows(data);
    } catch (err: any) {
      setError(err.message || "Failed to load workflows");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWorkflows();
  }, [loadWorkflows]);

  async function handleCreate() {
    if (!formName.trim()) return;
    setCreating(true);
    try {
      await api.createWorkflow({
        name: formName.trim(),
        use_case: formUseCase.trim() || null,
        execution_mode: formExecMode,
      });
      setFormName("");
      setFormUseCase("");
      setFormExecMode("sequential");
      setShowForm(false);
      await loadWorkflows();
    } catch (err: any) {
      setError(err.message || "Failed to create workflow");
    } finally {
      setCreating(false);
    }
  }

  async function handlePublish(id: string) {
    setPublishing(id);
    try {
      await api.publishWorkflow(id);
      await loadWorkflows();
    } catch (err: any) {
      setError(err.message || "Failed to publish workflow");
    } finally {
      setPublishing(null);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-ork-purple/30 border-t-ork-purple rounded-full animate-spin mx-auto" />
          <p className="data-label">LOADING WORKFLOW DEFINITIONS...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title text-sm mb-1">WORKFLOW DEFINITIONS</h1>
          <p className="text-ork-dim text-xs font-mono">
            Define and publish orchestration workflow templates
          </p>
        </div>
        <div className="flex items-center gap-3">
          {error && (
            <span className="text-[10px] font-mono text-ork-red bg-ork-red/10 border border-ork-red/20 rounded px-2 py-1">
              {error}
            </span>
          )}
          <button
            onClick={() => setShowForm(!showForm)}
            className="px-4 py-2 text-[11px] font-mono uppercase tracking-wider rounded-lg border border-ork-cyan/30 bg-ork-cyan/10 text-ork-cyan hover:bg-ork-cyan/20 transition-colors duration-150"
          >
            {showForm ? "CANCEL" : "CREATE WORKFLOW"}
          </button>
        </div>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="glass-panel p-5 glow-cyan animate-fade-in">
          <h2 className="section-title mb-4">NEW WORKFLOW DEFINITION</h2>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="data-label block mb-1.5">NAME *</label>
              <input
                type="text"
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="my-workflow"
                className="w-full bg-ork-bg border border-ork-border rounded-lg px-3 py-2 text-sm text-ork-text font-mono placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
              />
            </div>
            <div>
              <label className="data-label block mb-1.5">USE CASE</label>
              <input
                type="text"
                value={formUseCase}
                onChange={(e) => setFormUseCase(e.target.value)}
                placeholder="e.g. document_analysis"
                className="w-full bg-ork-bg border border-ork-border rounded-lg px-3 py-2 text-sm text-ork-text font-mono placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
              />
            </div>
            <div>
              <label className="data-label block mb-1.5">EXECUTION MODE</label>
              <select
                value={formExecMode}
                onChange={(e) => setFormExecMode(e.target.value)}
                className="w-full bg-ork-bg border border-ork-border rounded-lg px-3 py-2 text-sm text-ork-text font-mono focus:outline-none focus:border-ork-cyan/40"
              >
                <option value="sequential">Sequential</option>
                <option value="parallel">Parallel</option>
                <option value="dag">DAG</option>
              </select>
            </div>
          </div>
          <div className="flex justify-end mt-4">
            <button
              onClick={handleCreate}
              disabled={creating || !formName.trim()}
              className="px-5 py-2 text-[11px] font-mono uppercase tracking-wider rounded-lg border border-ork-green/30 bg-ork-green/10 text-ork-green hover:bg-ork-green/20 transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {creating ? "CREATING..." : "CREATE"}
            </button>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="glass-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className="border-b border-ork-border">
                {["ID", "NAME", "VERSION", "USE CASE", "EXECUTION MODE", "STATUS", "PUBLISHED AT", ""].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-[10px] font-mono uppercase tracking-wider text-ork-dim font-medium"
                    >
                      {h}
                    </th>
                  )
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-ork-border/50">
              {workflows.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-12 text-center">
                    <p className="text-ork-muted text-sm">No workflow definitions found</p>
                    <p className="text-ork-dim text-xs font-mono mt-1">
                      Create a workflow definition to get started
                    </p>
                  </td>
                </tr>
              ) : (
                workflows.map((w) => (
                  <tr
                    key={w.id}
                    className="hover:bg-ork-hover/50 transition-colors duration-100"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-ork-muted">
                      {w.id.slice(0, 8)}
                    </td>
                    <td className="px-4 py-3 text-sm text-ork-text font-medium">
                      {w.name}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs text-ork-muted">
                      {w.version}
                    </td>
                    <td className="px-4 py-3 text-xs text-ork-muted">
                      {w.use_case || "\u2014"}
                    </td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider bg-ork-purple/10 text-ork-purple border border-ork-purple/20 rounded">
                        {w.execution_mode}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={w.status} />
                    </td>
                    <td className="px-4 py-3 font-mono text-[11px] text-ork-dim whitespace-nowrap">
                      {w.published_at
                        ? new Date(w.published_at).toLocaleString()
                        : "\u2014"}
                    </td>
                    <td className="px-4 py-3">
                      {w.status !== "published" && (
                        <button
                          onClick={() => handlePublish(w.id)}
                          disabled={publishing === w.id}
                          className="px-3 py-1 text-[10px] font-mono uppercase tracking-wider rounded border border-ork-green/30 bg-ork-green/10 text-ork-green hover:bg-ork-green/20 transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
                        >
                          {publishing === w.id ? "..." : "PUBLISH"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
