"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { FlaskConical, Save } from "lucide-react";
import { request } from "@/lib/api-client";
import { listAgents } from "@/lib/agent-registry/service";
import type { AgentDefinition } from "@/lib/agent-registry/types";

export default function CreateScenarioPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedAgentId = searchParams.get("agent_id") || "";

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agents, setAgents] = useState<AgentDefinition[]>([]);

  const [name, setName] = useState("");
  const [agentId, setAgentId] = useState(preselectedAgentId);

  useEffect(() => {
    listAgents().then(setAgents).catch(() => {});
  }, []);
  const [description, setDescription] = useState("");
  const [inputPrompt, setInputPrompt] = useState("");
  const [timeoutSeconds, setTimeoutSeconds] = useState(120);
  const [maxIterations, setMaxIterations] = useState(5);
  const [assertionsJson, setAssertionsJson] = useState("[]");
  const [expectedToolsJson, setExpectedToolsJson] = useState("");
  const [tagsInput, setTagsInput] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    try {
      let assertions: any[];
      try {
        assertions = JSON.parse(assertionsJson);
      } catch {
        throw new Error("Assertions must be valid JSON array");
      }

      let expected_tools: string[] | undefined;
      if (expectedToolsJson.trim()) {
        try {
          expected_tools = JSON.parse(expectedToolsJson);
        } catch {
          throw new Error("Expected tools must be valid JSON array");
        }
      }

      const tags = tagsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);

      const payload = {
        name,
        agent_id: agentId,
        description: description || undefined,
        input_prompt: inputPrompt || undefined,
        timeout_seconds: timeoutSeconds,
        max_iterations: maxIterations,
        assertions,
        expected_tools,
        tags,
      };

      await request("/api/test-lab/scenarios", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      router.push("/test-lab");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const inputClasses =
    "w-full bg-ork-bg border border-ork-border rounded px-3 py-2 text-sm font-mono text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/50 transition-colors";
  const labelClasses = "data-label block mb-1.5";

  return (
    <div className="p-6 max-w-[800px] mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href="/test-lab"
          className="text-ork-muted hover:text-ork-cyan transition-colors text-xs font-mono"
        >
          TEST LAB /
        </Link>
        <div className="flex items-center gap-2">
          <FlaskConical size={16} className="text-ork-purple" />
          <h1 className="font-mono text-sm tracking-wide text-ork-text">
            Create Scenario
          </h1>
        </div>
      </div>

      {error && (
        <div className="glass-panel p-3 border-ork-red/30 bg-ork-red/5">
          <p className="text-ork-red text-xs font-mono">{error}</p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div>
          <h2 className="section-title mb-4">Basic Information</h2>
          <div className="glass-panel p-5 space-y-4">
            <div>
              <label className={labelClasses}>Name *</label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
                placeholder="e.g. email-summarizer-happy-path"
                className={inputClasses}
              />
            </div>
            <div>
              <label className={labelClasses}>Agent to test *</label>
              <select
                value={agentId}
                onChange={(e) => setAgentId(e.target.value)}
                required
                className={inputClasses}
              >
                <option value="">-- Select an agent --</option>
                {agents.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.id}) — {a.family_id} — {a.status}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className={labelClasses}>Description</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this scenario tests..."
                rows={3}
                className={inputClasses}
              />
            </div>
            <div>
              <label className={labelClasses}>Input Prompt</label>
              <textarea
                value={inputPrompt}
                onChange={(e) => setInputPrompt(e.target.value)}
                placeholder="The prompt to send to the agent..."
                rows={4}
                className={inputClasses}
              />
            </div>
          </div>
        </div>

        {/* Execution Config */}
        <div>
          <h2 className="section-title mb-4">Execution Configuration</h2>
          <div className="glass-panel p-5 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={labelClasses}>Timeout (seconds)</label>
                <input
                  type="number"
                  value={timeoutSeconds}
                  onChange={(e) => setTimeoutSeconds(parseInt(e.target.value) || 120)}
                  min={1}
                  className={inputClasses}
                />
              </div>
              <div>
                <label className={labelClasses}>Max Iterations</label>
                <input
                  type="number"
                  value={maxIterations}
                  onChange={(e) => setMaxIterations(parseInt(e.target.value) || 5)}
                  min={1}
                  className={inputClasses}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Assertions & Tools */}
        <div>
          <h2 className="section-title mb-4">Assertions & Expected Tools</h2>
          <div className="glass-panel p-5 space-y-4">
            <div>
              <label className={labelClasses}>Assertions (JSON array)</label>
              <textarea
                value={assertionsJson}
                onChange={(e) => setAssertionsJson(e.target.value)}
                placeholder='[{"type": "contains", "target": "output", "expected": "hello"}]'
                rows={6}
                className={inputClasses}
              />
              <p className="text-[10px] text-ork-dim font-mono mt-1">
                Array of assertion objects with type, target, expected, and optional operator fields.
              </p>
            </div>
            <div>
              <label className={labelClasses}>Expected Tools (JSON array)</label>
              <textarea
                value={expectedToolsJson}
                onChange={(e) => setExpectedToolsJson(e.target.value)}
                placeholder='["search_web", "send_email"]'
                rows={3}
                className={inputClasses}
              />
              <p className="text-[10px] text-ork-dim font-mono mt-1">
                Optional list of tool names the agent is expected to invoke.
              </p>
            </div>
          </div>
        </div>

        {/* Tags */}
        <div>
          <h2 className="section-title mb-4">Tags</h2>
          <div className="glass-panel p-5">
            <div>
              <label className={labelClasses}>Tags (comma-separated)</label>
              <input
                type="text"
                value={tagsInput}
                onChange={(e) => setTagsInput(e.target.value)}
                placeholder="smoke, regression, critical"
                className={inputClasses}
              />
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end gap-3">
          <Link
            href="/test-lab"
            className="px-4 py-1.5 text-xs font-mono uppercase tracking-wider text-ork-muted border border-ork-border rounded hover:bg-ork-hover transition-colors"
          >
            Cancel
          </Link>
          <button
            type="submit"
            disabled={saving || !name || !agentId}
            className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-mono uppercase tracking-wider bg-ork-cyan/15 text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/25 transition-colors disabled:opacity-50"
          >
            <Save size={13} />
            {saving ? "Saving..." : "Create Scenario"}
          </button>
        </div>
      </form>
    </div>
  );
}
