"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { api } from "@/lib/api";
import type { Request } from "@/lib/types";

const STATUS_FILTERS = ["all", "draft", "submitted", "accepted", "ready_for_planning", "planning"] as const;

export default function RequestsPage() {
  const [requests, setRequests] = useState<Request[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await api.listRequests(filter === "all" ? undefined : filter);
        setRequests(data);
      } catch (err: any) {
        setError(err.message || "Failed to load requests");
        setRequests([]);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [filter]);

  function formatDate(iso: string) {
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
          <h1>Requests</h1>
          <p>Incoming orchestration requests</p>
        </div>
        <div className="pagehead__actions">
          <Link
            href="/requests/new"
            className="btn btn--cyan"
          >
            + New Request
          </Link>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: "flex", alignItems: "center", gap: "6px", flexWrap: "wrap", marginBottom: "12px" }}>
        <span className="data-label" style={{ marginRight: "4px" }}>FILTER:</span>
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`btn${filter === s ? " btn--cyan" : ""}`}
            style={{ fontFamily: "var(--font-mono)", fontSize: "11px", textTransform: "uppercase", letterSpacing: "0.06em" }}
          >
            {s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="glass-panel" style={{ padding: "10px 14px", borderColor: "color-mix(in oklch, var(--ork-amber) 30%, transparent)", marginBottom: "10px" }}>
          <p style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-amber)", margin: 0 }}>
            {error}
          </p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "center", padding: "64px 0" }}>
          <div style={{ textAlign: "center" }}>
            <div className="w-6 h-6 border-2 border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin mx-auto" style={{ marginBottom: "10px" }} />
            <p className="section-title">LOADING REQUESTS...</p>
          </div>
        </div>
      )}

      {/* Table */}
      {!loading && requests.length > 0 && (
        <div className="tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>TITLE</th>
                <th>USE CASE</th>
                <th>CRITICALITY</th>
                <th>STATUS</th>
                <th>CREATED</th>
              </tr>
            </thead>
            <tbody>
              {requests.map((req) => (
                <tr key={req.id}>
                  <td className="col-id">{req.id.slice(0, 8)}</td>
                  <td className="col-name">{req.title}</td>
                  <td className="col-fam">{req.use_case || "--"}</td>
                  <td>
                    <StatusBadge status={req.criticality} />
                  </td>
                  <td>
                    <StatusBadge status={req.status} />
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: "12px", color: "var(--ork-muted-2)" }}>
                    {formatDate(req.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty state */}
      {!loading && requests.length === 0 && !error && (
        <div className="glass-panel" style={{ padding: "48px", textAlign: "center" }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
            <div style={{ width: "48px", height: "48px", borderRadius: "50%", border: "2px solid var(--ork-border)", display: "flex", alignItems: "center", justifyContent: "center" }}>
              <span style={{ color: "var(--ork-muted-2)", fontSize: "18px" }}>0</span>
            </div>
            <p style={{ color: "var(--ork-muted)", fontSize: "13px", margin: 0 }}>No requests found</p>
            <p style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--ork-muted-2)", margin: 0 }}>
              {filter !== "all"
                ? `No requests with status "${filter.replace(/_/g, " ")}"`
                : "Create your first request to get started"}
            </p>
            <Link
              href="/requests/new"
              className="btn btn--cyan"
            >
              + New Request
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
