"use client";

import type { AgentTestCaseInput, TestMode } from "@/lib/agent-test-lab/types";

interface TestCaseBuilderProps {
  value: AgentTestCaseInput;
  onChange: (updated: AgentTestCaseInput) => void;
}

const TEST_MODES: { value: TestMode; label: string }[] = [
  { value: "manual", label: "Manual" },
  { value: "template", label: "Template" },
  { value: "regression", label: "Regression" },
];

export function TestCaseBuilder({ value, onChange }: TestCaseBuilderProps) {
  function update<K extends keyof AgentTestCaseInput>(
    key: K,
    val: AgentTestCaseInput[K],
  ) {
    onChange({ ...value, [key]: val });
  }

  return (
    <div className="space-y-4">
      <h3 className="section-title">Test case</h3>

      {/* Mode */}
      <div>
        <label className="data-label block mb-1.5">Mode</label>
        <div className="flex gap-1.5">
          {TEST_MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => update("mode", m.value)}
              className={`px-3 py-1.5 text-[11px] font-mono uppercase tracking-wider rounded border transition-colors ${
                value.mode === m.value
                  ? "bg-ork-cyan/10 text-ork-cyan border-ork-cyan/30"
                  : "bg-ork-bg text-ork-muted border-ork-border hover:border-ork-dim"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {/* Title */}
      <div>
        <label className="data-label block mb-1.5">Title</label>
        <input
          type="text"
          value={value.title}
          onChange={(e) => update("title", e.target.value)}
          placeholder="e.g. Scope boundary test — off-topic query"
          className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40"
        />
      </div>

      {/* Task / instruction */}
      <div>
        <label className="data-label block mb-1.5">Task / instruction</label>
        <textarea
          value={value.task}
          onChange={(e) => update("task", e.target.value)}
          rows={4}
          placeholder="Describe the task or instruction to send to the agent..."
          className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40 resize-y"
        />
      </div>

      {/* Structured input JSON */}
      <div>
        <label className="data-label block mb-1.5">Structured input (JSON)</label>
        <textarea
          value={value.structuredInput}
          onChange={(e) => update("structuredInput", e.target.value)}
          rows={4}
          placeholder="{}"
          className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40 resize-y"
        />
      </div>

      {/* Evidence / documents */}
      <div>
        <label className="data-label block mb-1.5">Evidence / documents</label>
        <textarea
          value={value.evidence}
          onChange={(e) => update("evidence", e.target.value)}
          rows={3}
          placeholder="Paste reference documents, data, or evidence the agent should use..."
          className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40 resize-y"
        />
      </div>

      {/* Context variables */}
      <div>
        <label className="data-label block mb-1.5">Context variables (JSON)</label>
        <textarea
          value={value.contextVariables}
          onChange={(e) => update("contextVariables", e.target.value)}
          rows={3}
          placeholder='{"env": "staging", "user_role": "analyst"}'
          className="w-full px-3 py-2 text-xs font-mono bg-ork-bg border border-ork-border rounded text-ork-text placeholder:text-ork-dim focus:outline-none focus:border-ork-cyan/40 resize-y"
        />
      </div>
    </div>
  );
}
