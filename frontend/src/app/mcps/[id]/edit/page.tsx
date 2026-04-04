"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { getCatalogItem, updateOrkestraBindings } from "@/lib/mcp-catalog/service";
import type { OrkestraBindingUpdatePayload } from "@/lib/mcp-catalog/types";

function parseCsv(input: string): string[] {
  return input
    .split(",")
    .map((v) => v.trim())
    .filter((v) => v.length > 0);
}

export default function EditOrkestraBindingsPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [enabledInOrkestra, setEnabledInOrkestra] = useState(false);
  const [hiddenFromCatalog, setHiddenFromCatalog] = useState(false);
  const [hiddenFromAiGenerator, setHiddenFromAiGenerator] = useState(false);
  const [allowedAgentFamilies, setAllowedAgentFamilies] = useState("");
  const [allowedWorkflows, setAllowedWorkflows] = useState("");
  const [businessDomain, setBusinessDomain] = useState("");
  const [preferredUseCases, setPreferredUseCases] = useState("");
  const [riskLevelOverride, setRiskLevelOverride] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getCatalogItem(id)
      .then((item) => {
        if (cancelled) return;
        const binding = item.orkestra_binding;
        setName(item.obot_server.name);
        setEnabledInOrkestra(binding.enabled_in_orkestra);
        setHiddenFromCatalog(binding.hidden_from_catalog);
        setHiddenFromAiGenerator(binding.hidden_from_ai_generator);
        setAllowedAgentFamilies(binding.allowed_agent_families.join(", "));
        setAllowedWorkflows(binding.allowed_workflows.join(", "));
        setBusinessDomain(binding.business_domain ?? "");
        setPreferredUseCases(binding.preferred_use_cases.join(", "));
        setRiskLevelOverride(binding.risk_level_override ?? "");
        setNotes(binding.notes ?? "");
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setMessage(error instanceof Error ? error.message : "Failed to load binding");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function onSave(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setMessage(null);

    const payload: OrkestraBindingUpdatePayload = {
      enabled_in_orkestra: enabledInOrkestra,
      hidden_from_catalog: hiddenFromCatalog,
      hidden_from_ai_generator: hiddenFromAiGenerator,
      allowed_agent_families: parseCsv(allowedAgentFamilies),
      allowed_workflows: parseCsv(allowedWorkflows),
      business_domain: businessDomain.trim() || null,
      preferred_use_cases: parseCsv(preferredUseCases),
      risk_level_override: riskLevelOverride.trim() || null,
      notes: notes.trim() || null,
    };

    try {
      await updateOrkestraBindings(id, payload);
      setMessage("Orkestra bindings updated.");
    } catch (error: unknown) {
      setMessage(error instanceof Error ? error.message : "Failed to update bindings");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="p-6 max-w-3xl mx-auto">
        <div className="glass-panel p-12 text-center text-sm font-mono text-ork-cyan">
          Loading Orkestra bindings...
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-5 animate-fade-in">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link href={`/mcps/${id}`} className="text-xs font-mono text-ork-dim hover:text-ork-cyan">
            ← Back to MCP detail
          </Link>
          <h1 className="text-xl font-semibold mt-2">Edit Orkestra bindings</h1>
          <p className="text-xs font-mono text-ork-dim mt-1">
            MCP: <span className="text-ork-cyan">{name}</span> ({id})
          </p>
        </div>
      </div>

      {message && (
        <div className="glass-panel p-3">
          <p className="text-xs font-mono text-ork-muted">{message}</p>
        </div>
      )}

      <form onSubmit={onSave} className="glass-panel p-5 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex items-center gap-2 text-sm font-mono text-ork-text">
            <input
              type="checkbox"
              checked={enabledInOrkestra}
              onChange={(e) => setEnabledInOrkestra(e.target.checked)}
            />
            enabled_in_orkestra
          </label>
          <label className="flex items-center gap-2 text-sm font-mono text-ork-text">
            <input
              type="checkbox"
              checked={hiddenFromCatalog}
              onChange={(e) => setHiddenFromCatalog(e.target.checked)}
            />
            hidden_from_catalog
          </label>
          <label className="flex items-center gap-2 text-sm font-mono text-ork-text md:col-span-2">
            <input
              type="checkbox"
              checked={hiddenFromAiGenerator}
              onChange={(e) => setHiddenFromAiGenerator(e.target.checked)}
            />
            hidden_from_ai_generator
          </label>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="data-label">allowed_agent_families</p>
            <input
              value={allowedAgentFamilies}
              onChange={(e) => setAllowedAgentFamilies(e.target.value)}
              placeholder="research, compliance"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
            />
          </div>
          <div className="space-y-1">
            <p className="data-label">allowed_workflows</p>
            <input
              value={allowedWorkflows}
              onChange={(e) => setAllowedWorkflows(e.target.value)}
              placeholder="credit_review_default, due_diligence_v1"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="data-label">business_domain</p>
            <input
              value={businessDomain}
              onChange={(e) => setBusinessDomain(e.target.value)}
              placeholder="public_data_intelligence"
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
            />
          </div>
          <div className="space-y-1">
            <p className="data-label">risk_level_override</p>
            <select
              value={riskLevelOverride}
              onChange={(e) => setRiskLevelOverride(e.target.value)}
              className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
            >
              <option value="">none</option>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
            </select>
          </div>
        </div>

        <div className="space-y-1">
          <p className="data-label">preferred_use_cases</p>
          <input
            value={preferredUseCases}
            onChange={(e) => setPreferredUseCases(e.target.value)}
            placeholder="vendor due diligence, evidence collection"
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text"
          />
        </div>

        <div className="space-y-1">
          <p className="data-label">notes</p>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={5}
            placeholder="Governance notes and business constraints."
            className="w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm text-ork-text"
          />
        </div>

        <div className="flex items-center justify-end gap-2">
          <Link
            href={`/mcps/${id}`}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-border text-ork-muted"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving}
            className="px-3 py-2 text-xs font-mono uppercase tracking-wider rounded border border-ork-cyan/30 text-ork-cyan bg-ork-cyan/10 disabled:opacity-50"
          >
            {saving ? "Saving..." : "Save bindings"}
          </button>
        </div>
      </form>
    </div>
  );
}
