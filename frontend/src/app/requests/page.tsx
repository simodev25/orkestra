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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="section-title text-sm mb-1">REQUESTS</h1>
          <p className="text-ork-dim text-xs font-mono">
            Incoming orchestration requests
          </p>
        </div>
        <Link
          href="/requests/new"
          className="px-4 py-2 bg-ork-cyan/10 border border-ork-cyan/30 rounded-lg text-ork-cyan text-xs font-mono uppercase tracking-wider hover:bg-ork-cyan/20 hover:border-ork-cyan/50 transition-colors duration-200"
        >
          + New Request
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="data-label mr-1">FILTER:</span>
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1 text-[10px] font-mono uppercase tracking-wider rounded border transition-colors duration-200 ${
              filter === s
                ? "bg-ork-cyan/15 text-ork-cyan border-ork-cyan/30"
                : "bg-ork-bg text-ork-dim border-ork-border hover:border-ork-dim"
            }`}
          >
            {s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="glass-panel p-3 border-ork-amber/30">
          <p className="text-xs font-mono text-ork-amber">
            {error}
          </p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="text-center space-y-3">
            <div className="w-6 h-6 border-2 border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin mx-auto" />
            <p className="data-label">LOADING REQUESTS...</p>
          </div>
        </div>
      )}

      {/* Table */}
      {!loading && requests.length > 0 && (
        <div className="glass-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-ork-border">
                  <th className="text-left data-label px-4 py-3">ID</th>
                  <th className="text-left data-label px-4 py-3">TITLE</th>
                  <th className="text-left data-label px-4 py-3">USE CASE</th>
                  <th className="text-left data-label px-4 py-3">CRITICALITY</th>
                  <th className="text-left data-label px-4 py-3">STATUS</th>
                  <th className="text-left data-label px-4 py-3">CREATED</th>
                </tr>
              </thead>
              <tbody>
                {requests.map((req) => (
                  <tr
                    key={req.id}
                    className="border-b border-ork-border/50 hover:bg-ork-panel/50 transition-colors duration-150"
                  >
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-ork-cyan">
                        {req.id.slice(0, 8)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-sm text-ork-text">{req.title}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-ork-muted">
                        {req.use_case || "--"}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={req.criticality} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={req.status} />
                    </td>
                    <td className="px-4 py-3">
                      <span className="font-mono text-xs text-ork-dim">
                        {formatDate(req.created_at)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && requests.length === 0 && !error && (
        <div className="glass-panel p-12 text-center">
          <div className="space-y-3">
            <div className="w-12 h-12 rounded-full border-2 border-ork-border mx-auto flex items-center justify-center">
              <span className="text-ork-dim text-lg">0</span>
            </div>
            <p className="text-sm text-ork-muted">No requests found</p>
            <p className="text-xs text-ork-dim font-mono">
              {filter !== "all"
                ? `No requests with status "${filter.replace(/_/g, " ")}"`
                : "Create your first request to get started"}
            </p>
            <Link
              href="/requests/new"
              className="inline-block mt-2 px-4 py-2 bg-ork-cyan/10 border border-ork-cyan/30 rounded-lg text-ork-cyan text-xs font-mono uppercase tracking-wider hover:bg-ork-cyan/20 transition-colors"
            >
              + New Request
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
