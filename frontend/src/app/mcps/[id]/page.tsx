"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { StatusBadge } from "@/components/ui/status-badge";
import {
  bindToAgentFamily,
  bindToWorkflow,
  disableInOrkestra,
  enableInOrkestra,
  getCatalogItem,
} from "@/lib/mcp-catalog/service";
import type { CatalogMcpDetailsViewModel } from "@/lib/mcp-catalog/types";

function Field({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="data-label">{label}</p>
      <div className="text-sm text-ork-text">{value}</div>
    </div>
  );
}

export default function McpDetailsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [item, setItem] = useState<CatalogMcpDetailsViewModel | null>(null);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    setLoading(true);
    try {
      const data = await getCatalogItem(id);
      setItem(data);
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Failed to load MCP details");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!id) return;
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function runAction(action: () => Promise<void>) {
    setBusy(true);
    setMessage(null);
    try {
      await action();
      await reload();
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Action failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleBindWorkflow() {
    const workflowId = window.prompt("Workflow ID to bind:");
    if (!workflowId) return;
    await runAction(async () => {
      await bindToWorkflow(id, workflowId.trim());
      setMessage(`Bound to workflow ${workflowId.trim()}.`);
    });
  }

  async function handleBindAgentFamily() {
    const family = window.prompt("Agent family to bind:");
    if (!family) return;
    await runAction(async () => {
      await bindToAgentFamily(id, family.trim());
      setMessage(`Bound to agent family ${family.trim()}.`);
    });
  }

  if (loading) {
    return (
      <div className="p-6 max-w-[1300px] mx-auto">
        <div className="glass-panel p-14 text-center text-sm font-mono text-ork-cyan">Loading MCP details...</div>
      </div>
    );
  }

  if (!item) {
    return (
      <div className="p-6 max-w-[1300px] mx-auto">
        <div className="glass-panel p-12 text-center space-y-3">
          <p className="text-sm font-mono text-ork-red">{message ?? "MCP not found"}</p>
          <Link href="/mcps" className="text-xs font-mono text-ork-cyan hover:underline">
            Back to MCP Catalog
          </Link>
        </div>
      </div>
    );
  }

  const { obot_server: obot, orkestra_binding: binding } = item;

  return (
    <div className="p-6 max-w-[1300px] mx-auto space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <Link href="/mcps" className="text-xs font-mono text-ork-dim hover:text-ork-cyan">
            ← Back to MCP Catalog
          </Link>
          <h1 className="text-xl font-semibold mt-2">{obot.name}</h1>
          <p className="text-xs font-mono text-ork-dim mt-1">{obot.id}</p>
          <div className="flex items-center gap-2 mt-2 flex-wrap">
            <StatusBadge status={item.obot_state} />
            {obot.health_status && <StatusBadge status={obot.health_status} />}
            <StatusBadge status={item.orkestra_state} />
          </div>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <a
            href={obot.obot_url ?? "#"}
            target="_blank"
            rel="noreferrer"
            className={`px-3 py-2 text-xs font-mono uppercase tracking-wider border rounded ${
              obot.obot_url
                ? "border-ork-purple/30 text-ork-purple bg-ork-purple/10"
                : "border-ork-border text-ork-dim pointer-events-none"
            }`}
          >
            View in Obot
          </a>
          <button
            onClick={() =>
              runAction(async () => {
                if (binding.enabled_in_orkestra) {
                  await disableInOrkestra(id);
                  setMessage("Disabled in Orkestra.");
                } else {
                  await enableInOrkestra(id);
                  setMessage("Enabled in Orkestra.");
                }
              })
            }
            disabled={busy}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider border rounded border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 disabled:opacity-50"
          >
            {binding.enabled_in_orkestra ? "Disable in Orkestra" : "Enable in Orkestra"}
          </button>
          <button
            onClick={handleBindWorkflow}
            disabled={busy}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider border rounded border-ork-amber/30 text-ork-amber bg-ork-amber/10 disabled:opacity-50"
          >
            Bind to workflow
          </button>
          <button
            onClick={handleBindAgentFamily}
            disabled={busy}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider border rounded border-ork-green/30 text-ork-green bg-ork-green/10 disabled:opacity-50"
          >
            Bind to agent family
          </button>
          <Link
            href={`/mcps/${id}/edit`}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider border rounded border-ork-border text-ork-muted hover:text-ork-text"
          >
            Edit bindings
          </Link>
        </div>
      </div>

      {message && (
        <div className="glass-panel p-3">
          <p className="text-xs font-mono text-ork-muted">{message}</p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title">Block A — Obot Data</h2>
          <Field label="Name" value={obot.name} />
          <Field label="ID" value={<span className="font-mono">{obot.id}</span>} />
          <Field label="Purpose" value={obot.purpose} />
          <Field label="Description" value={obot.description ?? <span className="text-ork-dim italic">N/A</span>} />
          <div className="grid grid-cols-2 gap-4">
            <Field label="Technical state" value={<StatusBadge status={item.obot_state} />} />
            <Field label="Health" value={obot.health_status ? <StatusBadge status={obot.health_status} /> : "N/A"} />
            <Field label="Version" value={obot.version ?? "N/A"} />
            <Field label="Effect type" value={<span className="font-mono">{obot.effect_type}</span>} />
            <Field label="Criticality" value={<span className="font-mono">{obot.criticality}</span>} />
            <Field label="Approval required" value={obot.approval_required ? "Yes" : "No"} />
            <Field label="Usage (24h)" value={item.obot_server.usage_last_24h ?? "N/A"} />
            <Field label="Incidents (7d)" value={item.obot_server.incidents_last_7d ?? "N/A"} />
          </div>
          {item.obot_server.health_note && (
            <Field label="Health note" value={item.obot_server.health_note} />
          )}
          <div>
            <p className="data-label mb-1">Metadata</p>
            <pre className="bg-ork-bg border border-ork-border rounded p-3 text-[11px] font-mono text-ork-muted overflow-x-auto">
              {JSON.stringify(item.obot_server.metadata, null, 2)}
            </pre>
          </div>
        </section>

        <section className="glass-panel p-5 space-y-4">
          <h2 className="section-title">Block B — Orkestra Configuration</h2>
          <div className="grid grid-cols-2 gap-4">
            <Field label="enabled_in_orkestra" value={String(binding.enabled_in_orkestra)} />
            <Field label="hidden_from_catalog" value={String(binding.hidden_from_catalog)} />
            <Field label="hidden_from_ai_generator" value={String(binding.hidden_from_ai_generator)} />
            <Field label="business_domain" value={binding.business_domain ?? "N/A"} />
            <Field label="risk_level_override" value={binding.risk_level_override ?? "N/A"} />
            <Field label="Orkestra state" value={<StatusBadge status={item.orkestra_state} />} />
          </div>
          <Field
            label="allowed_agent_families"
            value={
              binding.allowed_agent_families.length > 0
                ? binding.allowed_agent_families.join(", ")
                : "None (not restricted)"
            }
          />
          <Field
            label="allowed_workflows"
            value={
              binding.allowed_workflows.length > 0
                ? binding.allowed_workflows.join(", ")
                : "None (not restricted)"
            }
          />
          <Field
            label="preferred_use_cases"
            value={
              binding.preferred_use_cases.length > 0
                ? binding.preferred_use_cases.join(", ")
                : "None"
            }
          />
          <Field label="notes" value={binding.notes ?? "None"} />
        </section>
      </div>
    </div>
  );
}
