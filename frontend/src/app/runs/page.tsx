"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { Run } from "@/lib/types";

const STATUS_OPTIONS = ["all", "planned", "running", "completed", "failed", "cancelled", "blocked"];

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    setLoading(true);
    setError(null);
    api
      .listRuns()
      .then(setRuns)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const filtered =
    statusFilter === "all" ? runs : runs.filter((r) => r.status === statusFilter);

  function formatCost(v: number | null | undefined) {
    if (v == null) return "--";
    return `$${v.toFixed(2)}`;
  }

  function formatDate(iso: string | null) {
    if (!iso) return "--";
    return new Date(iso).toLocaleString("en-US", {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  return (
    <div className="page animate-fade-in">
      {/* Header */}
      <div className="pagehead">
        <div>
          <h1>Runs</h1>
          <p>Execution instances across all cases</p>
        </div>
        <div className="pagehead__actions">
          <span className="section-title" style={{ lineHeight: "28px" }}>
            {filtered.length} run{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", gap: "6px", marginBottom: "12px", flexWrap: "wrap" }}>
        {STATUS_OPTIONS.map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`btn${statusFilter === s ? " btn--cyan" : ""}`}
            style={
              statusFilter !== s
                ? { fontFamily: "var(--font-mono)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.06em" }
                : { fontFamily: "var(--font-mono)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.06em" }
            }
          >
            {s}
          </button>
        ))}
      </div>

      {/* Content */}
      {loading ? (
        <div className="glass-panel" style={{ padding: "48px", textAlign: "center" }}>
          <div className="section-title animate-pulse-slow">Loading runs...</div>
        </div>
      ) : error ? (
        <div className="glass-panel" style={{ padding: "32px", textAlign: "center" }}>
          <p className="section-title" style={{ color: "var(--ork-red)" }}>Error: {error}</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="glass-panel" style={{ padding: "48px", textAlign: "center" }}>
          <p className="section-title">No runs found</p>
        </div>
      ) : (
        <div className="tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th>Run ID</th>
                <th>Case ID</th>
                <th>Plan ID</th>
                <th>Status</th>
                <th style={{ textAlign: "right" }}>Est. Cost</th>
                <th style={{ textAlign: "right" }}>Actual Cost</th>
                <th>Started At</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((run) => (
                <tr key={run.id}>
                  <td className="col-id">
                    <Link
                      href={`/runs/${run.id}`}
                      style={{ color: "var(--ork-cyan)" }}
                    >
                      {run.id.slice(0, 8)}...
                    </Link>
                  </td>
                  <td className="col-id">{run.case_id.slice(0, 8)}...</td>
                  <td className="col-id">{run.plan_id.slice(0, 8)}...</td>
                  <td>
                    <StatusBadge status={run.status} />
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-muted)" }}>
                    {formatCost(run.estimated_cost)}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                    {formatCost(run.actual_cost)}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-muted)" }}>
                    {formatDate(run.started_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
