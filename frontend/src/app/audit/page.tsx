"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { AuditEvent } from "@/lib/types";

const EVENT_COLORS: Record<string, string> = {
  "run.": "text-ork-cyan bg-ork-cyan/10 border-ork-cyan/20",
  "control.": "text-ork-amber bg-ork-amber/10 border-ork-amber/20",
  "approval.": "text-ork-purple bg-ork-purple/10 border-ork-purple/20",
  "agent.": "text-ork-green bg-ork-green/10 border-ork-green/20",
  "mcp.": "text-ork-red bg-ork-red/10 border-ork-red/20",
  "plan.": "text-ork-purple bg-ork-purple/10 border-ork-purple/20",
  "case.": "text-ork-cyan bg-ork-cyan/10 border-ork-cyan/20",
};

function getEventColor(eventType: string): string {
  for (const [prefix, color] of Object.entries(EVENT_COLORS)) {
    if (eventType.startsWith(prefix)) return color;
  }
  return "text-ork-muted bg-ork-dim/20 border-ork-dim/30";
}

export default function AuditPage() {
  const [runId, setRunId] = useState("");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState<Set<string>>(new Set());

  async function loadAudit() {
    if (!runId.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAuditTrail(runId.trim());
      const sorted = [...data].sort(
        (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
      );
      setEvents(sorted);
      setLoaded(true);
    } catch (err: any) {
      setError(err.message || "Failed to load audit trail");
      setEvents([]);
      setLoaded(true);
    } finally {
      setLoading(false);
    }
  }

  function toggleExpand(id: string) {
    setExpandedEvents((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="section-title text-sm mb-1">AUDIT &amp; REPLAY EXPLORER</h1>
        <p className="text-ork-dim text-xs font-mono">
          Full audit trail and event replay for any orchestration run
        </p>
      </div>

      {/* Search Bar */}
      <div className="glass-panel p-5">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="flex-1">
            <label className="data-label block mb-1.5">RUN ID</label>
            <input
              type="text"
              value={runId}
              onChange={(e) => setRunId(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && loadAudit()}
              placeholder="Enter run ID to load audit trail..."
              className="w-full bg-ork-bg border border-ork-border rounded-lg px-4 py-2.5 text-sm text-ork-text font-mono placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40 focus:ring-1 focus:ring-ork-cyan/20"
            />
          </div>
          <div className="flex items-end">
            <button
              onClick={loadAudit}
              disabled={loading || !runId.trim()}
              className="px-5 py-2.5 text-[11px] font-mono uppercase tracking-wider rounded-lg border border-ork-cyan/30 bg-ork-cyan/10 text-ork-cyan hover:bg-ork-cyan/20 transition-colors duration-150 disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 border border-ork-cyan/30 border-t-ork-cyan rounded-full animate-spin" />
                  LOADING...
                </span>
              ) : (
                "LOAD AUDIT TRAIL"
              )}
            </button>
          </div>
        </div>
        {error && (
          <p className="mt-3 text-xs font-mono text-ork-red bg-ork-red/10 border border-ork-red/20 rounded px-3 py-2">
            {error}
          </p>
        )}
      </div>

      {/* Timeline */}
      {loaded && (
        <div className="glass-panel p-5">
          <div className="flex items-center justify-between mb-5">
            <h2 className="section-title">
              TIMELINE &mdash; {events.length} EVENT{events.length !== 1 ? "S" : ""}
            </h2>
            {events.length > 0 && (
              <button
                onClick={() =>
                  setExpandedEvents((prev) =>
                    prev.size === events.length
                      ? new Set()
                      : new Set(events.map((e) => e.id))
                  )
                }
                className="text-[10px] font-mono text-ork-muted hover:text-ork-text transition-colors"
              >
                {expandedEvents.size === events.length ? "COLLAPSE ALL" : "EXPAND ALL"}
              </button>
            )}
          </div>

          {events.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-ork-muted text-sm">No audit events found for this run</p>
              <p className="text-ork-dim text-xs font-mono mt-1">
                Verify the Run ID and try again
              </p>
            </div>
          ) : (
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-[7px] top-3 bottom-3 w-px bg-ork-border" />

              <div className="space-y-1">
                {events.map((event, idx) => {
                  const isExpanded = expandedEvents.has(event.id);
                  const colorClass = getEventColor(event.event_type);

                  return (
                    <div key={event.id} className="relative pl-8 group">
                      {/* Timeline dot */}
                      <div
                        className={`absolute left-0 top-3 w-[15px] h-[15px] rounded-full border-2 bg-ork-surface ${
                          colorClass.split(" ")[0] === "text-ork-cyan"
                            ? "border-ork-cyan"
                            : colorClass.split(" ")[0] === "text-ork-amber"
                            ? "border-ork-amber"
                            : colorClass.split(" ")[0] === "text-ork-purple"
                            ? "border-ork-purple"
                            : colorClass.split(" ")[0] === "text-ork-green"
                            ? "border-ork-green"
                            : colorClass.split(" ")[0] === "text-ork-red"
                            ? "border-ork-red"
                            : "border-ork-dim"
                        }`}
                      />

                      <div
                        className="bg-ork-bg/50 rounded-lg p-3 border border-ork-border/30 hover:border-ork-border transition-colors cursor-pointer"
                        onClick={() => toggleExpand(event.id)}
                      >
                        <div className="flex items-center gap-3 flex-wrap">
                          {/* Timestamp */}
                          <span className="font-mono text-[11px] text-ork-dim whitespace-nowrap">
                            {new Date(event.timestamp).toLocaleTimeString("en-US", {
                              hour12: false,
                              hour: "2-digit",
                              minute: "2-digit",
                              second: "2-digit",
                            })}
                          </span>

                          {/* Event type badge */}
                          <span
                            className={`inline-flex items-center px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider border rounded ${colorClass}`}
                          >
                            {event.event_type}
                          </span>

                          {/* Actor */}
                          <span className="text-xs text-ork-muted">
                            <span className="text-ork-dim">{event.actor_type}</span>
                            {" / "}
                            <span className="font-mono text-ork-text">{event.actor_ref}</span>
                          </span>

                          {/* Expand indicator */}
                          <span className="ml-auto text-ork-dim text-xs font-mono">
                            {isExpanded ? "\u25B2" : "\u25BC"}
                          </span>
                        </div>

                        {/* Payload preview */}
                        {isExpanded && event.payload && (
                          <div className="mt-3 pt-3 border-t border-ork-border/30">
                            <p className="data-label mb-1.5">PAYLOAD</p>
                            <pre className="bg-ork-bg rounded-lg p-3 border border-ork-border/50 text-[11px] font-mono text-ork-muted overflow-x-auto max-h-64 overflow-y-auto">
                              {JSON.stringify(event.payload, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Placeholder when nothing loaded yet */}
      {!loaded && !loading && (
        <div className="glass-panel p-12 text-center">
          <div className="w-12 h-12 rounded-full border-2 border-ork-border flex items-center justify-center mx-auto mb-4">
            <span className="text-ork-dim text-lg font-mono">?</span>
          </div>
          <p className="text-ork-muted text-sm">Enter a Run ID to explore its audit trail</p>
          <p className="text-ork-dim text-xs font-mono mt-1">
            All governance events, state transitions, and actor actions are recorded
          </p>
        </div>
      )}
    </div>
  );
}
