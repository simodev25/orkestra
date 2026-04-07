"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";
import { FlaskConical, Play, CheckCircle, XCircle } from "lucide-react";

interface Assertion {
  type: string;
  target: string;
  expected: any;
  operator?: string;
}

interface Scenario {
  id: string;
  name: string;
  agent_id: string;
  description?: string;
  input_prompt?: string;
  timeout_seconds: number;
  max_iterations: number;
  assertions: Assertion[];
  expected_tools?: string[];
  tags: string[];
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

interface ScenarioRun {
  id: string;
  scenario_id: string;
  status: string;
  verdict: string;
  score: number | null;
  duration_ms: number | null;
  created_at: string;
  finished_at: string | null;
}

function formatDate(iso: string | null) {
  if (!iso) return "--";
  return new Date(iso).toLocaleString("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export default function ScenarioDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [runs, setRuns] = useState<ScenarioRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningAction, setRunningAction] = useState(false);

  const fetchData = useCallback(() => {
    if (!id) return;
    Promise.all([
      fetch(`/api/test-lab/scenarios/${id}`).then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      }),
      fetch(`/api/test-lab/runs?scenario_id=${id}`).then((r) => {
        if (!r.ok) return [];
        return r.json();
      }),
    ])
      .then(([scenarioData, runsData]) => {
        setScenario(scenarioData);
        setRuns(runsData);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function handleRun() {
    if (!id) return;
    setRunningAction(true);
    try {
      const res = await fetch(`/api/test-lab/scenarios/${id}/run`, {
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
      setRunningAction(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-16 text-center">
          <div className="text-ork-cyan font-mono text-sm animate-pulse">
            Loading scenario...
          </div>
        </div>
      </div>
    );
  }

  if (error && !scenario) {
    return (
      <div className="p-6 max-w-[1200px] mx-auto">
        <div className="glass-panel p-8 text-center">
          <p className="text-ork-red font-mono text-sm">Error: {error}</p>
          <Link href="/test-lab" className="text-ork-cyan text-xs font-mono mt-3 inline-block hover:underline">
            Back to Test Lab
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            href="/test-lab"
            className="text-ork-muted hover:text-ork-cyan transition-colors text-xs font-mono"
          >
            TEST LAB /
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <FlaskConical size={16} className="text-ork-purple" />
              <h1 className="font-mono text-sm tracking-wide text-ork-text">
                {scenario?.name}
              </h1>
              <StatusBadge status={scenario?.enabled ? "active" : "disabled"} />
            </div>
            <p className="text-[10px] text-ork-dim font-mono mt-0.5">
              Agent: {scenario?.agent_id.slice(0, 12)} &middot; ID: {id?.slice(0, 12)}
            </p>
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={runningAction}
          className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-green/15 text-ork-green border border-ork-green/30 rounded hover:bg-ork-green/25 transition-colors disabled:opacity-50"
        >
          <Play size={13} />
          {runningAction ? "Starting..." : "Run Scenario"}
        </button>
      </div>

      {error && (
        <div className="glass-panel p-3 border-ork-red/30 bg-ork-red/5">
          <p className="text-ork-red text-xs font-mono">{error}</p>
        </div>
      )}

      {/* Scenario Metadata */}
      <div>
        <h2 className="section-title mb-4">Scenario Details</h2>
        <div className="glass-panel p-5">
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="data-label mb-1">Description</p>
              <p className="text-sm text-ork-text">
                {scenario?.description || <span className="text-ork-dim italic">No description</span>}
              </p>
            </div>
            <div className="space-y-3">
              <div className="flex gap-6">
                <div>
                  <p className="data-label mb-1">Timeout</p>
                  <p className="text-sm font-mono text-ork-text">{scenario?.timeout_seconds}s</p>
                </div>
                <div>
                  <p className="data-label mb-1">Max Iterations</p>
                  <p className="text-sm font-mono text-ork-text">{scenario?.max_iterations}</p>
                </div>
              </div>
              <div>
                <p className="data-label mb-1">Tags</p>
                <div className="flex gap-1 flex-wrap">
                  {scenario?.tags?.length ? (
                    scenario.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-[10px] font-mono text-ork-purple bg-ork-purple/10 border border-ork-purple/20 px-1.5 py-0.5 rounded"
                      >
                        {tag}
                      </span>
                    ))
                  ) : (
                    <span className="text-ork-dim text-xs font-mono">None</span>
                  )}
                </div>
              </div>
            </div>
          </div>
          {scenario?.input_prompt && (
            <div className="mt-4 pt-4 border-t border-ork-border">
              <p className="data-label mb-2">Input Prompt</p>
              <pre className="bg-ork-bg border border-ork-border rounded p-3 text-xs font-mono text-ork-muted whitespace-pre-wrap max-h-[200px] overflow-y-auto">
                {scenario.input_prompt}
              </pre>
            </div>
          )}
          {scenario?.expected_tools && scenario.expected_tools.length > 0 && (
            <div className="mt-4 pt-4 border-t border-ork-border">
              <p className="data-label mb-2">Expected Tools</p>
              <div className="flex gap-1.5 flex-wrap">
                {scenario.expected_tools.map((tool) => (
                  <span
                    key={tool}
                    className="text-[10px] font-mono text-ork-cyan bg-ork-cyan/10 border border-ork-cyan/20 px-2 py-0.5 rounded"
                  >
                    {tool}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Assertions */}
      <div>
        <h2 className="section-title mb-4">Assertions ({scenario?.assertions?.length ?? 0})</h2>
        <div className="glass-panel overflow-hidden">
          {!scenario?.assertions?.length ? (
            <p className="text-ork-muted font-mono text-xs text-center py-8">
              No assertions defined
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ork-border">
                  <th className="data-label text-left px-4 py-2.5">Type</th>
                  <th className="data-label text-left px-4 py-2.5">Target</th>
                  <th className="data-label text-left px-4 py-2.5">Operator</th>
                  <th className="data-label text-left px-4 py-2.5">Expected</th>
                </tr>
              </thead>
              <tbody>
                {scenario.assertions.map((a, i) => (
                  <tr key={i} className="border-b border-ork-border/50">
                    <td className="px-4 py-2.5 font-mono text-ork-text">{a.type}</td>
                    <td className="px-4 py-2.5 font-mono text-ork-muted">{a.target}</td>
                    <td className="px-4 py-2.5 font-mono text-ork-dim">{a.operator || "--"}</td>
                    <td className="px-4 py-2.5 font-mono text-ork-muted max-w-[300px] truncate">
                      {typeof a.expected === "string" ? a.expected : JSON.stringify(a.expected)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Recent Runs */}
      <div>
        <h2 className="section-title mb-4">Recent Runs</h2>
        <div className="glass-panel overflow-hidden">
          {runs.length === 0 ? (
            <p className="text-ork-muted font-mono text-xs text-center py-8">
              No runs yet. Click "Run Scenario" to execute a test.
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-ork-border">
                  <th className="data-label text-left px-4 py-2.5">Run ID</th>
                  <th className="data-label text-left px-4 py-2.5">Status</th>
                  <th className="data-label text-left px-4 py-2.5">Verdict</th>
                  <th className="data-label text-left px-4 py-2.5">Score</th>
                  <th className="data-label text-left px-4 py-2.5">Duration</th>
                  <th className="data-label text-left px-4 py-2.5">Created</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.id}
                    className="border-b border-ork-border/50 hover:bg-ork-hover/30 transition-colors"
                  >
                    <td className="px-4 py-2.5">
                      <Link
                        href={`/test-lab/runs/${run.id}`}
                        className="font-mono text-ork-cyan hover:underline"
                      >
                        {run.id.slice(0, 12)}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="px-4 py-2.5">
                      {run.verdict ? (
                        <span className="flex items-center gap-1">
                          {run.verdict === "pass" ? (
                            <CheckCircle size={12} className="text-ork-green" />
                          ) : (
                            <XCircle size={12} className="text-ork-red" />
                          )}
                          <StatusBadge status={run.verdict === "pass" ? "passed" : "failed"} />
                        </span>
                      ) : (
                        <span className="text-ork-dim font-mono">--</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-text">
                      {run.score != null ? `${(run.score * 100).toFixed(0)}%` : "--"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-dim">
                      {run.duration_ms != null ? `${(run.duration_ms / 1000).toFixed(1)}s` : "--"}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-ork-dim">
                      {formatDate(run.created_at)}
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
