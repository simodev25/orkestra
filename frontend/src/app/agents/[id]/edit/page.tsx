"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AgentForm } from "@/components/agents/agent-form";
import { getAgent, listAvailableSkills, listMcpCatalogForAgentDesign, updateAgent } from "@/lib/agent-registry/service";
import type {
  AgentCreatePayload,
  AgentDefinition,
  AgentUpdatePayload,
  McpCatalogSummary,
} from "@/lib/agent-registry/types";

export default function EditAgentPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = params.id;

  const [agent, setAgent] = useState<AgentDefinition | null>(null);
  const [catalogMcps, setCatalogMcps] = useState<McpCatalogSummary[]>([]);
  const [availableSkills, setAvailableSkills] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([getAgent(id), listMcpCatalogForAgentDesign(), listAvailableSkills()])
      .then(([agentValue, catalog, skills]) => {
        if (cancelled) return;
        setAgent(agentValue);
        setCatalogMcps(catalog);
        setAvailableSkills(skills);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load agent");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function handleSubmit(payload: AgentCreatePayload | AgentUpdatePayload) {
    setSaving(true);
    setError(null);
    try {
      await updateAgent(id, payload as AgentUpdatePayload);
      router.push(`/agents/${id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update agent");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">Loading agent edit view...</div>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="glass-panel p-6 text-sm font-mono text-ork-red">{error ?? "Agent not found"}</div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4 animate-fade-in">
      <div className="flex items-start justify-between">
        <div>
          <Link href={`/agents/${id}`} className="text-xs font-mono text-ork-dim hover:text-ork-cyan">
            ← Back to Agent detail
          </Link>
          <h1 className="text-xl font-semibold mt-2">Edit Agent</h1>
          <p className="text-xs font-mono text-ork-dim mt-1">
            Update governed fields, prompt, skills file, and MCP permissions.
          </p>
        </div>
      </div>

      {error && (
        <div className="glass-panel p-3 border border-ork-red/30">
          <p className="text-xs font-mono text-ork-red">{error}</p>
        </div>
      )}

      <AgentForm
        mode="edit"
        initial={agent}
        availableMcps={catalogMcps}
        availableSkills={availableSkills}
        submitLabel="Save agent changes"
        saving={saving}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
