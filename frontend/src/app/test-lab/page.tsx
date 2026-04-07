"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import { FlaskConical, Play, Eye, Plus } from "lucide-react";

interface Scenario {
  id: string;
  name: string;
  agent_id: string;
  description?: string;
  input_prompt?: string;
  timeout_seconds: number;
  max_iterations: number;
  assertions: any[];
  expected_tools?: string[];
  tags: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export default function TestLabPage() {
  const router = useRouter();
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningId, setRunningId] = useState<string | null>(null);

  const fetchScenarios = useCallback(() => {
    fetch("/api/test-lab/scenarios")
      .then((res) => {
        if (!res.ok) throw new Error(res.statusText);
        return res.json();
      })
      .then((data) => {
        setScenarios(data);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchScenarios();
  }, [fetchScenarios]);

  async function handleRun(scenarioId: string) {
    setRunningId(scenarioId);
    try {
      const res = await fetch(`/api/test-lab/scenarios/${scenarioId}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || res.statusText);
      }
      const run = await res.json();
      router.push(`/test-lab/runs/${run.id}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunningId(null);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-16 text-center">
          <div className="text-ork-cyan font-mono text-sm animate-pulse">
            Loading scenarios...
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <FlaskConical size={18} className="text-ork-purple" />
          <h1 className="font-mono text-sm tracking-wide text-ork-text uppercase">
            Agentic Test Lab
          </h1>
        </div>
        <Link
          href="/test-lab/scenarios/new"
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-cyan/15 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/25 transition-colors"
        >
          <Plus size={13} />
          Create Scenario
        </Link>
      </div>

      {error && (
        <div className="glass-panel p-3 border-ork-red/30 bg-ork-red/5">
          <p className="text-ork-red text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Scenarios Table */}
      <div>
        <h2 className="section-title mb-4">Scenarios</h2>
        <div className="glass-panel overflow-hidden">
          {scenarios.length === 0 ? (
            <p className="text-ork-muted font-mono text-xs text-center py-12">
              No scenarios yet. Create one to get started.
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ork-border">
                  <th className="data-label text-left px-4 py-2.5">Name</th>
                  <th className="data-label text-left px-4 py-2.5">Agent</th>
                  <th className="data-label text-left px-4 py-2.5">Assertions</th>
                  <th className="data-label text-left px-4 py-2.5">Timeout</th>
                  <th className="data-label text-left px-4 py-2.5">Tags</th>
                  <th className="data-label text-left px-4 py-2.5">Enabled</th>
                  <th className="data-label text-left px-4 py-2.5">Actions</th>
                </tr>
              </thead>
              <tbody>
                {scenarios.map((s) => (
                  <tr
                    key={s.id}
                    className="border-b border-ork-border/50 hover:bg-ork-hover/30 transition-colors"
                  >
                    <td className="px-4 py-2.5 font-mono text-ork-text font-medium">
                      {s.name}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-muted">
                      {s.agent_id.slice(0, 12)}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-muted">
                      {s.assertions?.length ?? 0}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-dim">
                      {s.timeout_seconds}s
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex gap-1 flex-wrap">
                        {s.tags?.map((tag) => (
                          <span
                            key={tag}
                            className="text-[10px] font-mono text-ork-purple bg-ork-purple/10 border border-ork-purple/20 px-1.5 py-0.5 rounded"
                          >
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusBadge status={s.enabled ? "active" : "disabled"} />
                    </td>
                    <td className="px-4 py-2.5">
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/test-lab/scenarios/${s.id}`}
                          className="flex items-center gap-1 text-ork-cyan hover:text-ork-cyan/80 transition-colors font-mono"
                        >
                          <Eye size={12} />
                          View
                        </Link>
                        <button
                          onClick={() => handleRun(s.id)}
                          disabled={runningId === s.id}
                          className="flex items-center gap-1 px-2 py-0.5 text-[10px] font-mono uppercase tracking-wider bg-ork-green/15 text-ork-green border border-ork-green/30 rounded hover:bg-ork-green/25 transition-colors disabled:opacity-50"
                        >
                          <Play size={10} />
                          {runningId === s.id ? "Starting..." : "Run"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
