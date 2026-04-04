"use client";

import { useState, useEffect, useCallback } from "react";
import { StatusBadge } from "@/components/ui/status-badge";
import { StatCard } from "@/components/ui/stat-card";
import { api } from "@/lib/api";
import type { Approval } from "@/lib/types";

const STATUSES = ["all", "requested", "pending", "approved", "rejected"] as const;

export default function ApprovalsPage() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [comments, setComments] = useState<Record<string, string>>({});

  const loadApprovals = useCallback(async () => {
    try {
      const data = await api.listApprovals(
        statusFilter === "all" ? undefined : statusFilter
      );
      setApprovals(data);
    } catch (err: any) {
      setError(err.message || "Failed to load approvals");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    setLoading(true);
    loadApprovals();
  }, [loadApprovals]);

  async function handleApprove(id: string) {
    setActionLoading(id);
    try {
      await api.approveApproval(id, comments[id] || "");
      await loadApprovals();
    } catch (err: any) {
      setError(err.message || "Failed to approve");
    } finally {
      setActionLoading(null);
    }
  }

  async function handleReject(id: string) {
    setActionLoading(id);
    try {
      await api.rejectApproval(id, comments[id] || "");
      await loadApprovals();
    } catch (err: any) {
      setError(err.message || "Failed to reject");
    } finally {
      setActionLoading(null);
    }
  }

  const pendingCount = approvals.filter(
    (a) => a.status === "pending" || a.status === "requested"
  ).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full min-h-[60vh]">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-2 border-ork-amber/30 border-t-ork-amber rounded-full animate-spin mx-auto" />
          <p className="data-label">LOADING APPROVAL WORKBENCH...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title text-sm mb-1">APPROVAL WORKBENCH</h1>
          <p className="text-ork-dim text-xs font-mono">
            Review and action pending governance approvals
          </p>
        </div>
        <div className="flex items-center gap-3">
          {error && (
            <span className="text-[10px] font-mono text-ork-red bg-ork-red/10 border border-ork-red/20 rounded px-2 py-1">
              {error}
            </span>
          )}
          {pendingCount > 0 && (
            <div className="flex items-center gap-2 bg-ork-amber/10 border border-ork-amber/20 rounded-lg px-3 py-1.5">
              <div className="w-2 h-2 rounded-full bg-ork-amber glow-dot animate-pulse-slow" />
              <span className="font-mono text-xs text-ork-amber">
                {pendingCount} PENDING
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="TOTAL APPROVALS" value={approvals.length} accent="cyan" />
        <StatCard
          label="PENDING / REQUESTED"
          value={pendingCount}
          accent="amber"
        />
        <StatCard
          label="APPROVED"
          value={approvals.filter((a) => a.status === "approved").length}
          accent="green"
        />
        <StatCard
          label="REJECTED"
          value={approvals.filter((a) => a.status === "rejected").length}
          accent="red"
        />
      </div>

      {/* Filter */}
      <div className="glass-panel p-4 flex items-center gap-2">
        <span className="data-label mr-2">STATUS</span>
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider rounded border transition-colors duration-150 ${
              statusFilter === s
                ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                : "border-ork-border text-ork-muted hover:text-ork-text hover:border-ork-dim"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Approval Cards */}
      {approvals.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <p className="text-ork-muted text-sm">No approvals found</p>
          <p className="text-ork-dim text-xs font-mono mt-1">
            Approval requests appear when governance policies require human review
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {approvals.map((a) => {
            const isPending = a.status === "pending" || a.status === "requested";
            return (
              <div
                key={a.id}
                className={`glass-panel-hover p-5 space-y-4 ${
                  isPending ? "border-l-2 border-l-ork-amber/40" : ""
                }`}
              >
                {/* Card header */}
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-ork-purple uppercase tracking-wider">
                        {a.approval_type}
                      </span>
                      <StatusBadge status={a.status} />
                    </div>
                    <p className="text-sm text-ork-text">{a.reason}</p>
                  </div>
                </div>

                {/* Metadata */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="data-label mb-0.5">RUN ID</p>
                    <p className="font-mono text-xs text-ork-cyan">{a.run_id.slice(0, 12)}</p>
                  </div>
                  <div>
                    <p className="data-label mb-0.5">CASE ID</p>
                    <p className="font-mono text-xs text-ork-cyan">{a.case_id.slice(0, 12)}</p>
                  </div>
                  <div>
                    <p className="data-label mb-0.5">REVIEWER ROLE</p>
                    <p className="text-xs text-ork-text">{a.reviewer_role || "\u2014"}</p>
                  </div>
                  <div>
                    <p className="data-label mb-0.5">ASSIGNED TO</p>
                    <p className="text-xs text-ork-text">{a.assigned_to || "\u2014"}</p>
                  </div>
                </div>

                {/* Timestamps */}
                <div className="flex items-center gap-4 text-[10px] font-mono text-ork-dim">
                  {a.requested_at && (
                    <span>REQ: {new Date(a.requested_at).toLocaleString()}</span>
                  )}
                  {a.resolved_at && (
                    <span>RES: {new Date(a.resolved_at).toLocaleString()}</span>
                  )}
                </div>

                {/* Decision comment if resolved */}
                {a.decision_comment && (
                  <div className="bg-ork-bg rounded-lg p-3 border border-ork-border/50">
                    <p className="data-label mb-1">DECISION COMMENT</p>
                    <p className="text-xs text-ork-text">{a.decision_comment}</p>
                  </div>
                )}

                {/* Actions for pending items */}
                {isPending && (
                  <div className="space-y-3 pt-2 border-t border-ork-border/50">
                    <input
                      type="text"
                      placeholder="Optional comment..."
                      value={comments[a.id] || ""}
                      onChange={(e) =>
                        setComments((prev) => ({ ...prev, [a.id]: e.target.value }))
                      }
                      className="w-full bg-ork-bg border border-ork-border rounded px-3 py-1.5 text-xs text-ork-text font-mono placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApprove(a.id)}
                        disabled={actionLoading === a.id}
                        className="flex-1 px-3 py-2 text-[11px] font-mono uppercase tracking-wider rounded border border-ork-green/30 bg-ork-green/10 text-ork-green hover:bg-ork-green/20 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {actionLoading === a.id ? "..." : "APPROVE"}
                      </button>
                      <button
                        onClick={() => handleReject(a.id)}
                        disabled={actionLoading === a.id}
                        className="flex-1 px-3 py-2 text-[11px] font-mono uppercase tracking-wider rounded border border-ork-red/30 bg-ork-red/10 text-ork-red hover:bg-ork-red/20 transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {actionLoading === a.id ? "..." : "REJECT"}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
