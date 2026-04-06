"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import { TestCaseBuilder } from "@/components/agents/test-lab/TestCaseBuilder";
import { ExpectedBehaviors } from "@/components/agents/test-lab/ExpectedBehaviors";
import { ExecutionResult } from "@/components/agents/test-lab/ExecutionResult";
import { QualificationGate } from "@/components/agents/test-lab/QualificationGate";
import { RecentRuns } from "@/components/agents/test-lab/RecentRuns";
import { getAgent, updateAgentStatus } from "@/lib/agent-registry/service";
import { executeTestRun } from "@/lib/agent-test-lab/mock-runner";
import { createEmptyTestCase } from "@/lib/agent-test-lab/types";
import type { AgentDefinition } from "@/lib/agent-registry/types";
import type { AgentTestCaseInput, AgentTestRunResult } from "@/lib/agent-test-lab/types";
import { FlaskConical, Play, RotateCcw, Save, Repeat2 } from "lucide-react";

export default function AgentTestLabPage() {
  const params = useParams<{ id: string }>();
  const agentId = params.id;

  const [agent, setAgent] = useState<AgentDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [testCase, setTestCase] = useState<AgentTestCaseInput>(createEmptyTestCase());
  const [currentResult, setCurrentResult] = useState<AgentTestRunResult | null>(null);
  const [runs, setRuns] = useState<AgentTestRunResult[]>([]);
  const [running, setRunning] = useState(false);
  const [promoting, setPromoting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getAgent(agentId)
      .then((a) => {
        if (!cancelled) setAgent(a);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load agent");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [agentId]);

  const handleRun = useCallback(
    async (count: number = 1) => {
      if (!agent) return;
      setRunning(true);
      setError(null);
      try {
        let lastResult: AgentTestRunResult | null = null;
        for (let i = 0; i < count; i++) {
          const result = await executeTestRun(agent.id, agent.version, testCase);
          // Fix total token count
          if (result.tokenUsage) {
            result.tokenUsage.total = result.tokenUsage.input + result.tokenUsage.output;
          }
          lastResult = result;
          setRuns((prev) => [result, ...prev]);
        }
        setCurrentResult(lastResult);
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "Test execution failed");
      } finally {
        setRunning(false);
      }
    },
    [agent, testCase],
  );

  const handleReset = useCallback(() => {
    setTestCase(createEmptyTestCase());
    setCurrentResult(null);
  }, []);

  const handlePromote = useCallback(async () => {
    if (!agent) return;
    setPromoting(true);
    setError(null);
    try {
      const updated = await updateAgentStatus(agent.id, "tested");
      setAgent(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Promotion failed");
    } finally {
      setPromoting(false);
    }
  }, [agent]);

  if (loading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">
          Loading agent...
        </div>
      </div>
    );
  }

  if (error && !agent) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="glass-panel p-6 text-sm font-mono text-ork-red">{error}</div>
      </div>
    );
  }

  if (!agent) return null;

  return (
    <div className="p-6 max-w-7xl mx-auto animate-fade-in">
      {/* ── Header ────────────────────────────────────────────────── */}
      <div className="mb-6">
        <Link
          href={`/agents/${agent.id}`}
          className="text-xs font-mono text-ork-dim hover:text-ork-cyan"
        >
          ← Back to {agent.name}
        </Link>

        <div className="flex items-start justify-between mt-2">
          <div>
            <div className="flex items-center gap-3">
              <FlaskConical size={20} className="text-ork-cyan" />
              <h1 className="text-xl font-semibold">Agent Test Lab</h1>
            </div>
            <p className="text-xs font-mono text-ork-dim mt-1">
              {agent.id} · v{agent.version} · {agent.llm_provider || "no provider"}/{agent.llm_model || "no model"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <StatusBadge status={agent.status} />
            <StatusBadge status={agent.last_test_status || "not_tested"} />
          </div>
        </div>

        <p className="text-[11px] text-ork-muted mt-2 max-w-2xl">
          Qualify the behavioral response of this agent in isolation. Define a test scenario,
          declare expected behaviors, execute, and review. If all checks pass, promote the agent
          to <span className="text-ork-cyan">tested</span>.
        </p>
      </div>

      {error && (
        <div className="glass-panel p-3 border-ork-red/30 mb-4">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      {/* ── Main layout: left = builder, right = results ──────── */}
      <div className="grid grid-cols-1 lg:grid-cols-[420px_1fr] gap-6">
        {/* Left column: Test case builder + behaviors */}
        <div className="space-y-5">
          <div className="glass-panel p-4">
            <TestCaseBuilder value={testCase} onChange={setTestCase} />
          </div>

          <div className="glass-panel p-4">
            <ExpectedBehaviors
              value={testCase.expectedBehaviors}
              onChange={(behaviors) =>
                setTestCase((prev) => ({ ...prev, expectedBehaviors: behaviors }))
              }
            />
          </div>

          {/* Action buttons */}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => handleRun(1)}
              disabled={running || !testCase.task.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider rounded border bg-ork-cyan/10 text-ork-cyan border-ork-cyan/30 hover:bg-ork-cyan/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Play size={13} /> Run once
            </button>
            <button
              onClick={() => handleRun(5)}
              disabled={running || !testCase.task.trim()}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider rounded border bg-ork-purple/10 text-ork-purple border-ork-purple/30 hover:bg-ork-purple/20 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Repeat2 size={13} /> Run 5x
            </button>
            <button
              disabled={running}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider rounded border bg-ork-surface text-ork-muted border-ork-border hover:text-ork-text hover:border-ork-dim transition-colors disabled:opacity-40"
            >
              <Save size={13} /> Save case
            </button>
            <button
              onClick={handleReset}
              disabled={running}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono uppercase tracking-wider rounded border bg-ork-surface text-ork-muted border-ork-border hover:text-ork-text hover:border-ork-dim transition-colors disabled:opacity-40"
            >
              <RotateCcw size={13} /> Reset
            </button>
          </div>
        </div>

        {/* Right column: Result + qualification + runs */}
        <div className="space-y-5">
          <ExecutionResult result={currentResult} running={running} />

          <div className="glass-panel p-4">
            <QualificationGate
              currentStatus={agent.status}
              runs={runs}
              onPromote={handlePromote}
              promoting={promoting}
            />
          </div>

          <RecentRuns runs={runs} />
        </div>
      </div>
    </div>
  );
}
