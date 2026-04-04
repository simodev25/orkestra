"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AgentForm } from "@/components/agents/agent-form";
import { createAgent, listMcpCatalogForAgentDesign } from "@/lib/agent-registry/service";
import type {
  AgentCreatePayload,
  AgentUpdatePayload,
  McpCatalogSummary,
} from "@/lib/agent-registry/types";

export default function NewAgentPage() {
  const router = useRouter();
  const [catalogMcps, setCatalogMcps] = useState<McpCatalogSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listMcpCatalogForAgentDesign()
      .then((items) => {
        if (!cancelled) setCatalogMcps(items);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load MCP catalog");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(payload: AgentCreatePayload | AgentUpdatePayload) {
    setSaving(true);
    setError(null);
    try {
      const created = await createAgent(payload as AgentCreatePayload);
      router.push(`/agents/${created.id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to create agent");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">Loading form context...</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4 animate-fade-in">
      <div className="flex items-start justify-between">
        <div>
          <Link href="/agents" className="text-xs font-mono text-ork-dim hover:text-ork-cyan">
            ← Back to Agent Registry
          </Link>
          <h1 className="text-xl font-semibold mt-2">Add Agent</h1>
          <p className="text-xs font-mono text-ork-dim mt-1">
            Create a governed agent definition. New agents must start in draft/designed.
          </p>
        </div>
      </div>

      {error && (
        <div className="glass-panel p-3 border border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      <AgentForm
        mode="create"
        availableMcps={catalogMcps}
        submitLabel="Create agent"
        saving={saving}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
