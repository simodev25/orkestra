"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { FlaskConical, Save, Plus, Trash2 } from "lucide-react";
import { request } from "@/lib/api-client";
import { listAgents } from "@/lib/agent-registry/service";
import type { AgentDefinition } from "@/lib/agent-registry/types";

// Supported assertion types (must match app/services/test_lab/assertion_engine.py)
type AssertionType =
  | "tool_called"
  | "tool_not_called"
  | "output_field_exists"
  | "output_schema_matches"
  | "max_duration_ms"
  | "max_iterations"
  | "final_status_is"
  | "no_tool_failures";

type AssertionRow = {
  type: AssertionType;
  target: string;
  expected: string;
  critical: boolean;
};

const ASSERTION_DEFS: Record<
  AssertionType,
  { label: string; hint: string; showTarget: boolean; showExpected: boolean; targetLabel?: string; expectedLabel?: string; expectedPlaceholder?: string }
> = {
  tool_called: {
    label: "Tool called",
    hint: "Verify that a specific tool was invoked by the agent.",
    showTarget: true,
    showExpected: false,
    targetLabel: "Tool name",
  },
  tool_not_called: {
    label: "Tool NOT called",
    hint: "Verify that a specific tool was NEVER invoked by the agent.",
    showTarget: true,
    showExpected: false,
    targetLabel: "Tool name",
  },
  output_field_exists: {
    label: "Output field exists",
    hint: "Parse the agent output as JSON and verify a field is present.",
    showTarget: true,
    showExpected: false,
    targetLabel: "Field name",
  },
  output_schema_matches: {
    label: "Output schema matches",
    hint: "Verify the output JSON has all required fields listed in the schema.",
    showTarget: false,
    showExpected: true,
    expectedLabel: "JSON schema",
    expectedPlaceholder: '{"required": ["siren", "company_name"]}',
  },
  max_duration_ms: {
    label: "Max duration (ms)",
    hint: "Verify the total run duration is below the given threshold.",
    showTarget: false,
    showExpected: true,
    expectedLabel: "Max duration in ms",
    expectedPlaceholder: "30000",
  },
  max_iterations: {
    label: "Max iterations",
    hint: "Verify the ReAct loop did not exceed N iterations.",
    showTarget: false,
    showExpected: true,
    expectedLabel: "Max iterations",
    expectedPlaceholder: "8",
  },
  final_status_is: {
    label: "Final status equals",
    hint: "Verify the target agent's final run status matches.",
    showTarget: false,
    showExpected: true,
    expectedLabel: "Expected status",
    expectedPlaceholder: "completed",
  },
  no_tool_failures: {
    label: "No tool failures",
    hint: "Verify no tool call raised an error during execution.",
    showTarget: false,
    showExpected: false,
  },
};

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
  const [assertions, setAssertions] = useState<AssertionRow[]>([]);
  const [expectedToolsInput, setExpectedToolsInput] = useState("");
  const [tagsInput, setTagsInput] = useState("");

  function addAssertion() {
    setAssertions((prev) => [
      ...prev,
      { type: "tool_called", target: "", expected: "", critical: false },
    ]);
  }

  function removeAssertion(index: number) {
    setAssertions((prev) => prev.filter((_, i) => i !== index));
  }

  function updateAssertion(index: number, patch: Partial<AssertionRow>) {
    setAssertions((prev) =>
      prev.map((a, i) => (i === index ? { ...a, ...patch } : a))
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);

    try {
      // Serialize assertions to the backend format.
      // IMPORTANT: the backend schema (app/schemas/test_lab.py AssertionDef)
      // requires `expected` to be a string (Optional[str]). Numeric assertion
      // types (max_duration_ms, max_iterations) are parsed as int server-side
      // via assertion_engine._check_max_duration(int(expected or 0)).
      const assertionsPayload = assertions.map((a) => {
        const def = ASSERTION_DEFS[a.type];
        const entry: any = { type: a.type };
        if (def.showTarget) entry.target = a.target || null;
        if (def.showExpected) {
          // Always send as string — never as number.
          const val = (a.expected ?? "").toString().trim();
          entry.expected = val || null;
        }
        if (a.critical) entry.critical = true;
        return entry;
      });

      // Expected tools: accept comma-separated list OR JSON array
      let expected_tools: string[] | undefined;
      const etRaw = expectedToolsInput.trim();
      if (etRaw) {
        if (etRaw.startsWith("[")) {
          try {
            expected_tools = JSON.parse(etRaw);
          } catch {
            throw new Error("Expected tools JSON array is invalid");
          }
        } else {
          expected_tools = etRaw
            .split(",")
            .map((t) => t.trim())
            .filter(Boolean);
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
        assertions: assertionsPayload,
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
          <div className="glass-panel p-5 space-y-5">
            {/* Assertions editor */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className={labelClasses + " !mb-0"}>
                  Assertions ({assertions.length})
                </label>
                <button
                  type="button"
                  onClick={addAssertion}
                  className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-ork-cyan border border-ork-cyan/30 rounded hover:bg-ork-cyan/10 transition-colors"
                >
                  <Plus size={11} />
                  Add Assertion
                </button>
              </div>

              {assertions.length === 0 ? (
                <p className="text-[10px] text-ork-dim font-mono italic py-3 text-center border border-dashed border-ork-border/40 rounded">
                  No assertions yet — the LLM Judge will still score the run, but no
                  deterministic rules will be evaluated. Click &quot;Add Assertion&quot; to
                  add rules (e.g. &quot;tool_called&quot;, &quot;max_duration_ms&quot;).
                </p>
              ) : (
                <div className="space-y-3">
                  {assertions.map((a, idx) => {
                    const def = ASSERTION_DEFS[a.type];
                    return (
                      <div
                        key={idx}
                        className="border border-ork-border/50 rounded p-3 space-y-2 bg-ork-bg/40"
                      >
                        <div className="flex items-start gap-2">
                          <div className="flex-1">
                            <label className="text-[9px] text-ork-dim font-mono uppercase tracking-wider block mb-1">
                              Type
                            </label>
                            <select
                              value={a.type}
                              onChange={(e) =>
                                updateAssertion(idx, {
                                  type: e.target.value as AssertionType,
                                  // Reset target/expected when type changes so the
                                  // UI stays consistent with the new type's fields.
                                  target: "",
                                  expected: "",
                                })
                              }
                              className={inputClasses + " !text-xs"}
                            >
                              {(Object.keys(ASSERTION_DEFS) as AssertionType[]).map(
                                (t) => (
                                  <option key={t} value={t}>
                                    {ASSERTION_DEFS[t].label} ({t})
                                  </option>
                                )
                              )}
                            </select>
                          </div>
                          <button
                            type="button"
                            onClick={() => removeAssertion(idx)}
                            className="mt-[22px] p-1.5 text-ork-red/70 hover:text-ork-red hover:bg-ork-red/10 rounded transition-colors"
                            title="Remove assertion"
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>

                        <p className="text-[10px] text-ork-dim font-mono italic">
                          {def.hint}
                        </p>

                        {def.showTarget && (
                          <div>
                            <label className="text-[9px] text-ork-dim font-mono uppercase tracking-wider block mb-1">
                              {def.targetLabel || "Target"}
                            </label>
                            <input
                              type="text"
                              value={a.target}
                              onChange={(e) =>
                                updateAssertion(idx, { target: e.target.value })
                              }
                              placeholder={
                                a.type === "tool_called" || a.type === "tool_not_called"
                                  ? "e.g. search_datasets"
                                  : a.type === "output_field_exists"
                                  ? "e.g. siren"
                                  : ""
                              }
                              className={inputClasses + " !text-xs"}
                            />
                          </div>
                        )}

                        {def.showExpected && (
                          <div>
                            <label className="text-[9px] text-ork-dim font-mono uppercase tracking-wider block mb-1">
                              {def.expectedLabel || "Expected"}
                            </label>
                            <input
                              type={
                                a.type === "max_duration_ms" ||
                                a.type === "max_iterations"
                                  ? "number"
                                  : "text"
                              }
                              value={a.expected}
                              onChange={(e) =>
                                updateAssertion(idx, { expected: e.target.value })
                              }
                              placeholder={def.expectedPlaceholder || ""}
                              className={inputClasses + " !text-xs"}
                            />
                          </div>
                        )}

                        <label className="flex items-center gap-2 cursor-pointer mt-1">
                          <input
                            type="checkbox"
                            checked={a.critical}
                            onChange={(e) =>
                              updateAssertion(idx, { critical: e.target.checked })
                            }
                            className="accent-ork-red"
                          />
                          <span className="text-[10px] font-mono text-ork-dim">
                            Critical — fail the whole run if this assertion fails
                          </span>
                        </label>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Expected tools */}
            <div>
              <label className={labelClasses}>Expected Tools</label>
              <input
                type="text"
                value={expectedToolsInput}
                onChange={(e) => setExpectedToolsInput(e.target.value)}
                placeholder="search_datasets, get_dataset_info"
                className={inputClasses}
              />
              <p className="text-[10px] text-ork-dim font-mono mt-1">
                Optional comma-separated list of tools the agent is expected to invoke.
                Leave empty for no constraint.
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
