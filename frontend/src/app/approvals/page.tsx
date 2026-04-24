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
      <div className="page animate-fade-in" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
        <div style={{ textAlign: "center" }}>
          <div className="w-8 h-8 border-2 border-ork-amber/30 border-t-ork-amber rounded-full animate-spin mx-auto" style={{ marginBottom: "10px" }} />
          <p className="section-title">LOADING APPROVAL WORKBENCH...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page animate-fade-in">
      {/* Header */}
      <div className="pagehead">
        <div>
          <h1>Approval Workbench</h1>
          <p>Review and action pending governance approvals</p>
        </div>
        <div className="pagehead__actions">
          {error && (
            <span style={{ fontSize: "11px", fontFamily: "var(--font-mono)", color: "var(--ork-red)", background: "var(--ork-red-bg)", border: "1px solid color-mix(in oklch, var(--ork-red) 25%, transparent)", borderRadius: "var(--radius)", padding: "3px 8px" }}>
              {error}
            </span>
          )}
          {pendingCount > 0 && (
            <div style={{ display: "flex", alignItems: "center", gap: "6px", background: "var(--ork-amber-bg)", border: "1px solid color-mix(in oklch, var(--ork-amber) 25%, transparent)", borderRadius: "var(--radius)", padding: "4px 10px" }}>
              <div className="glow-dot animate-pulse-slow" style={{ color: "var(--ork-amber)" }} />
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--ork-amber)" }}>
                {pendingCount} PENDING
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Summary */}
      <div className="stats" style={{ marginBottom: "12px" }}>
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
      <div className="glass-panel" style={{ padding: "10px 12px", display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px", flexWrap: "wrap" }}>
        <span className="data-label" style={{ marginRight: "4px" }}>STATUS</span>
        {STATUSES.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`btn${statusFilter === s ? " btn--cyan" : ""}`}
            style={{ fontFamily: "var(--font-mono)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.06em" }}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Approval Cards */}
      {approvals.length === 0 ? (
        <div className="glass-panel" style={{ padding: "48px", textAlign: "center" }}>
          <p style={{ color: "var(--ork-muted)", fontSize: "13px" }}>No approvals found</p>
          <p style={{ color: "var(--ork-muted-2)", fontSize: "11px", fontFamily: "var(--font-mono)", marginTop: "4px" }}>
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
                className={`glass-panel glass-panel-hover${isPending ? " border-l-2 border-l-ork-amber/40" : ""}`}
                style={{ padding: "14px 16px" }}
              >
                {/* Card header */}
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "10px", marginBottom: "12px" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--ork-purple)", textTransform: "uppercase", letterSpacing: "0.06em" }}>
                        {a.approval_type}
                      </span>
                      <StatusBadge status={a.status} />
                    </div>
                    <p style={{ fontSize: "13px", color: "var(--ork-text)", margin: 0 }}>{a.reason}</p>
                  </div>
                </div>

                {/* Metadata KV */}
                <div className="kv" style={{ marginBottom: "10px" }}>
                  <span className="k">RUN ID</span>
                  <span className="v cyan">{a.run_id.slice(0, 12)}</span>
                  <span className="k">CASE ID</span>
                  <span className="v cyan">{a.case_id.slice(0, 12)}</span>
                  <span className="k">REVIEWER ROLE</span>
                  <span className="v">{a.reviewer_role || "\u2014"}</span>
                  <span className="k">ASSIGNED TO</span>
                  <span className="v">{a.assigned_to || "\u2014"}</span>
                </div>

                {/* Timestamps */}
                <div style={{ display: "flex", gap: "16px", fontFamily: "var(--font-mono)", fontSize: "10px", color: "var(--ork-muted-2)", marginBottom: "8px" }}>
                  {a.requested_at && (
                    <span>REQ: {new Date(a.requested_at).toLocaleString()}</span>
                  )}
                  {a.resolved_at && (
                    <span>RES: {new Date(a.resolved_at).toLocaleString()}</span>
                  )}
                </div>

                {/* Decision comment if resolved */}
                {a.decision_comment && (
                  <div style={{ background: "var(--ork-bg)", borderRadius: "var(--radius)", padding: "10px 12px", border: "1px solid var(--ork-border)", marginBottom: "8px" }}>
                    <p className="data-label" style={{ marginBottom: "4px" }}>DECISION COMMENT</p>
                    <p style={{ fontSize: "12px", color: "var(--ork-text)", margin: 0 }}>{a.decision_comment}</p>
                  </div>
                )}

                {/* Actions for pending items */}
                {isPending && (
                  <div style={{ paddingTop: "10px", borderTop: "1px solid var(--ork-border)", display: "flex", flexDirection: "column", gap: "8px" }}>
                    <input
                      type="text"
                      placeholder="Optional comment..."
                      value={comments[a.id] || ""}
                      onChange={(e) =>
                        setComments((prev) => ({ ...prev, [a.id]: e.target.value }))
                      }
                      className="field"
                      style={{ width: "100%" }}
                    />
                    <div style={{ display: "flex", gap: "6px" }}>
                      <button
                        onClick={() => handleApprove(a.id)}
                        disabled={actionLoading === a.id}
                        className="btn"
                        style={{
                          flex: 1,
                          color: "var(--ork-green)",
                          background: "var(--ork-green-bg)",
                          borderColor: "color-mix(in oklch, var(--ork-green) 30%, transparent)",
                          opacity: actionLoading === a.id ? 0.5 : 1,
                          cursor: actionLoading === a.id ? "not-allowed" : undefined,
                          fontFamily: "var(--font-mono)",
                          fontSize: "11px",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          justifyContent: "center",
                        }}
                      >
                        {actionLoading === a.id ? "..." : "APPROVE"}
                      </button>
                      <button
                        onClick={() => handleReject(a.id)}
                        disabled={actionLoading === a.id}
                        className="btn btn--red"
                        style={{
                          flex: 1,
                          opacity: actionLoading === a.id ? 0.5 : 1,
                          cursor: actionLoading === a.id ? "not-allowed" : undefined,
                          fontFamily: "var(--font-mono)",
                          fontSize: "11px",
                          textTransform: "uppercase",
                          letterSpacing: "0.06em",
                          justifyContent: "center",
                        }}
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
