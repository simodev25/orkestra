"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { StatusBadge } from "@/components/ui/status-badge";
import { listAgents } from "@/lib/agent-registry/service";
import type { AgentDefinition } from "@/lib/agent-registry/types";
import { FlaskConical, ArrowRight } from "lucide-react";

export default function TestLabIndexPage() {
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listAgents()
      .then(setAgents)
      .catch(() => setAgents([]))
      .finally(() => setLoading(false));
  }, []);

  const testableAgents = agents.filter((a) =>
    ["draft", "designed", "tested", "registered", "active"].includes(a.status),
  );

  return (
    <div className="p-6 max-w-4xl mx-auto animate-fade-in">
      <div className="flex items-center gap-3 mb-1">
        <FlaskConical size={20} className="text-ork-cyan" />
        <h1 className="text-xl font-semibold">Agent Test Lab</h1>
      </div>
      <p className="text-xs text-ork-muted mb-6">
        Select an agent to open its behavioral qualification lab.
      </p>

      {loading ? (
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">
          Loading agents...
        </div>
      ) : testableAgents.length === 0 ? (
        <div className="glass-panel p-8 text-center text-xs font-mono text-ork-dim">
          No testable agents found.
        </div>
      ) : (
        <div className="space-y-2">
          {testableAgents.map((agent) => (
            <Link
              key={agent.id}
              href={`/agents/${agent.id}/test-lab`}
              className="glass-panel-hover flex items-center justify-between p-4 group"
            >
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-semibold text-ork-text group-hover:text-ork-cyan transition-colors">
                    {agent.name}
                  </span>
                  <StatusBadge status={agent.status} />
                  <StatusBadge status={agent.last_test_status || "not_tested"} />
                </div>
                <p className="text-xs font-mono text-ork-dim">
                  {agent.id} · v{agent.version}
                </p>
              </div>
              <ArrowRight
                size={16}
                className="text-ork-dim group-hover:text-ork-cyan transition-colors"
              />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
