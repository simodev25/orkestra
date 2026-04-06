"use client";

import { Check, Lock, Circle } from "lucide-react";
import type { MainStepDisplay } from "@/lib/agent-lifecycle/types";
import type { LifecycleGate } from "@/lib/agent-lifecycle/types";

interface PromotionPathProps {
  steps: MainStepDisplay[];
  gates: (LifecycleGate | null)[];
}

const STEP_STYLES: Record<
  MainStepDisplay["state"],
  { dot: string; label: string; line: string }
> = {
  done: {
    dot: "bg-ork-green text-ork-bg",
    label: "text-ork-green",
    line: "bg-ork-green/40",
  },
  current: {
    dot: "bg-ork-cyan text-ork-bg ring-4 ring-ork-cyan/20",
    label: "text-ork-cyan font-semibold",
    line: "bg-ork-border",
  },
  locked: {
    dot: "bg-ork-border text-ork-dim",
    label: "text-ork-dim",
    line: "bg-ork-border",
  },
};

export function PromotionPath({ steps, gates }: PromotionPathProps) {
  return (
    <div className="glass-panel p-5">
      <h3 className="section-title mb-5">Promotion path</h3>

      <div className="flex items-start justify-between relative">
        {steps.map((step, i) => {
          const style = STEP_STYLES[step.state];
          const gate = i > 0 ? gates[i - 1] : null;

          return (
            <div key={step.step} className="flex items-start flex-1 last:flex-none">
              {/* Gate connector (between steps) */}
              {i > 0 && (
                <div className="flex-1 flex flex-col items-center pt-3 -mx-1">
                  <div className={`h-0.5 w-full ${style.line}`} />
                  {gate && (
                    <span className="text-[9px] font-mono text-ork-dim mt-1.5 text-center leading-tight px-1">
                      {gate.title}
                    </span>
                  )}
                </div>
              )}

              {/* Step node */}
              <div className="flex flex-col items-center gap-2 min-w-[72px]">
                <div
                  className={`w-7 h-7 rounded-full flex items-center justify-center transition-all ${style.dot}`}
                >
                  {step.state === "done" && <Check size={14} strokeWidth={2.5} />}
                  {step.state === "current" && <Circle size={10} fill="currentColor" />}
                  {step.state === "locked" && <Lock size={12} />}
                </div>
                <span className={`text-[11px] font-mono uppercase tracking-wider ${style.label}`}>
                  {step.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
