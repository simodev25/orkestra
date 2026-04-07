"use client";

import type { AgentTestCaseInput, BehavioralCheckKey } from "@/lib/agent-test-lab/types";
import { BEHAVIORAL_CHECKS } from "@/lib/agent-test-lab/types";

interface ExpectedBehaviorsProps {
  value: AgentTestCaseInput["expectedBehaviors"];
  onChange: (updated: AgentTestCaseInput["expectedBehaviors"]) => void;
}

export function ExpectedBehaviors({ value, onChange }: ExpectedBehaviorsProps) {
  function toggle(key: BehavioralCheckKey) {
    onChange({ ...value, [key]: !value[key] });
  }

  return (
    <div className="space-y-3">
      <h3 className="section-title">Expected behaviors</h3>
      <p className="text-[10px] text-ork-dim">
        Select which behavioral checks to evaluate during this test run.
      </p>

      <div className="space-y-1.5">
        {BEHAVIORAL_CHECKS.map((check) => {
          const checked = value[check.key] ?? false;
          return (
            <label
              key={check.key}
              className="flex items-start gap-2.5 p-2 rounded border border-transparent hover:border-ork-border cursor-pointer group transition-colors"
            >
              <input
                type="checkbox"
                checked={checked}
                onChange={() => toggle(check.key)}
                className="mt-0.5 accent-ork-cyan"
              />
              <div className="flex-1 min-w-0">
                <span className="text-xs font-mono text-ork-text group-hover:text-ork-cyan transition-colors">
                  {check.label}
                </span>
                <p className="text-[10px] text-ork-dim leading-relaxed">
                  {check.description}
                </p>
              </div>
            </label>
          );
        })}
      </div>
    </div>
  );
}
