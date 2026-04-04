"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useParams } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import { getAgent, listMcpCatalogForAgentDesign } from "@/lib/agent-registry/service";
import type { AgentDefinition, McpCatalogSummary } from "@/lib/agent-registry/types";

export default function AgentDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [agent, setAgent] = useState<AgentDefinition | null>(null);
  const [catalogMcps, setCatalogMcps] = useState<McpCatalogSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([getAgent(id), listMcpCatalogForAgentDesign()])
      .then(([agentValue, mcpCatalog]) => {
        if (cancelled) return;
        setAgent(agentValue);
        setCatalogMcps(mcpCatalog);
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

  const mcpMap = useMemo(() => {
    const map = new Map<string, McpCatalogSummary>();
    for (const mcp of catalogMcps) map.set(mcp.id, mcp);
    return map;
  }, [catalogMcps]);

  if (loading) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="glass-panel p-16 text-center text-sm font-mono text-ork-cyan">Loading agent details...</div>
      </div>
    );
  }

  if (error || !agent) {
    return (
      <div className="p-6 max-w-5xl mx-auto">
        <div className="glass-panel p-6 text-sm font-mono text-ork-red">{error ?? "Agent not found"}</div>
      </div>
    );
  }

  const skills = agent.skills ?? [];
  const allowedMcps = agent.allowed_mcps ?? [];
  const forbiddenEffects = agent.forbidden_effects ?? [];
  const limitations = agent.limitations ?? [];

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4 animate-fade-in">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href="/agents" className="text-xs font-mono text-ork-dim hover:text-ork-cyan">
            ← Back to Agent Registry
          </Link>
          <h1 className="text-xl font-semibold mt-2">{agent.name}</h1>
          <p className="text-xs font-mono text-ork-dim mt-1">
            {agent.id} · family={agent.family}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <StatusBadge status={agent.status} />
          <Link
            href={`/agents/${agent.id}/edit`}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-purple/30 text-ork-purple bg-ork-purple/10"
          >
            Edit
          </Link>
        </div>
      </div>

      <Section title="Identity">
        <KV label="name" value={agent.name} />
        <KV label="agent_id" value={agent.id} mono />
        <KV label="family" value={agent.family} />
        <KV label="version" value={agent.version} mono />
        <KV label="status" value={agent.status} mono />
        <KV label="owner" value={agent.owner || "-"} mono />
      </Section>

      <Section title="Mission / Description">
        <KV label="purpose" value={agent.purpose} />
        <KV label="description" value={agent.description || "-"} />
      </Section>

      <Section title="Skills">
        <KV label="skills" value={skills.length > 0 ? skills.join(", ") : "-"} />
      </Section>

      <Section title="Selection hints">
        <pre className="text-xs font-mono text-ork-muted whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3">
{JSON.stringify(agent.selection_hints ?? {}, null, 2)}
        </pre>
      </Section>

      <Section title="MCP permissions">
        {allowedMcps.length === 0 ? (
          <p className="text-sm text-ork-dim font-mono">No allowed MCPs configured.</p>
        ) : (
          <div className="space-y-2">
            {allowedMcps.map((mcpId) => {
              const mcp = mcpMap.get(mcpId);
              return (
                <div key={mcpId} className="border border-ork-border rounded p-2 text-xs font-mono">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-ork-cyan">{mcpId}</span>
                    {mcp ? (
                      <>
                        <span className="text-ork-text">{mcp.name}</span>
                        <span className="text-ork-dim">{mcp.effect_type}</span>
                        <StatusBadge status={mcp.orkestra_state} />
                        <StatusBadge status={mcp.obot_state} />
                      </>
                    ) : (
                      <span className="text-ork-dim">not present in current catalog snapshot</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
        <KV label="forbidden_effects" value={forbiddenEffects.length > 0 ? forbiddenEffects.join(", ") : "-"} />
      </Section>

      <Section title="Contracts">
        <KV label="input_contract_ref" value={agent.input_contract_ref || "-"} mono />
        <KV label="output_contract_ref" value={agent.output_contract_ref || "-"} mono />
      </Section>

      <Section title="Prompt">
        <KV label="prompt_ref" value={agent.prompt_ref || "-"} mono />
        <pre className="text-xs font-mono text-ork-text whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3">
{agent.prompt_content || "-"}
        </pre>
      </Section>

      <Section title="Skills file">
        <KV label="skills_ref" value={agent.skills_ref || "-"} mono />
        <pre className="text-xs font-mono text-ork-text whitespace-pre-wrap bg-ork-bg border border-ork-border rounded p-3">
{agent.skills_content || "-"}
        </pre>
      </Section>

      <Section title="Limitations">
        <KV label="limitations" value={limitations.length > 0 ? limitations.join(", ") : "-"} />
      </Section>

      <Section title="Reliability / Tests">
        <KV label="last_test_status" value={agent.last_test_status || "not_tested"} mono />
        <KV label="last_validated_at" value={agent.last_validated_at || "-"} mono />
      </Section>

      <Section title="Usage metadata">
        <KV label="usage_count" value={String(agent.usage_count)} mono />
        <KV label="criticality" value={agent.criticality} />
        <KV label="cost_profile" value={agent.cost_profile} />
        <KV label="created_at" value={agent.created_at} mono />
        <KV label="updated_at" value={agent.updated_at} mono />
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="glass-panel p-4 space-y-2">
      <h2 className="section-title text-sm">{title}</h2>
      {children}
    </section>
  );
}

function KV({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="grid grid-cols-[180px_1fr] gap-3 items-start text-xs">
      <p className="data-label">{label}</p>
      <p className={`${mono ? "font-mono" : ""} text-ork-text`}>{value}</p>
    </div>
  );
}
