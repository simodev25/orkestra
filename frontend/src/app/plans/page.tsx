"use client";

import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/ui/status-badge";

export default function PlansPage() {
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    // Plans don't have a direct list endpoint — we show recent runs with their plans
    fetch("/api/runs")
      .then((r) => r.ok ? r.json() : Promise.reject("Failed to fetch"))
      .then((runs) => {
        setPlans(runs.filter((r: any) => r.plan_id));
        setLoading(false);
      })
      .catch(() => { setError("Could not load plans"); setLoading(false); });
  }, []);

  return (
    <div className="p-8 animate-fade-in">
      <h1 className="section-title text-lg mb-6">ORCHESTRATION PLANS</h1>

      {loading ? (
        <p className="text-ork-muted font-mono text-sm">Loading...</p>
      ) : error ? (
        <p className="text-ork-red font-mono text-sm">{error}</p>
      ) : plans.length === 0 ? (
        <div className="glass-panel p-12 text-center">
          <p className="text-ork-muted">No plans yet. Create a request and generate a plan.</p>
        </div>
      ) : (
        <div className="glass-panel overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ork-border text-left">
                <th className="data-label p-3">Run ID</th>
                <th className="data-label p-3">Plan ID</th>
                <th className="data-label p-3">Case ID</th>
                <th className="data-label p-3">Status</th>
                <th className="data-label p-3">Est. Cost</th>
                <th className="data-label p-3">Created</th>
              </tr>
            </thead>
            <tbody>
              {plans.map((run: any) => (
                <tr key={run.id} className="border-b border-ork-border/50 hover:bg-ork-hover transition-colors">
                  <td className="p-3 font-mono text-xs text-ork-cyan">{run.id?.slice(0, 16)}</td>
                  <td className="p-3 font-mono text-xs text-ork-muted">{run.plan_id?.slice(0, 16)}</td>
                  <td className="p-3 font-mono text-xs text-ork-muted">{run.case_id?.slice(0, 16)}</td>
                  <td className="p-3"><StatusBadge status={run.status} /></td>
                  <td className="p-3 font-mono text-xs">${run.estimated_cost?.toFixed(2) ?? "—"}</td>
                  <td className="p-3 text-xs text-ork-muted">{new Date(run.created_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
