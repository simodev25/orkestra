"use client";

import { Check, Lock } from "lucide-react";
import type { MainStepDisplay } from "@/lib/agent-lifecycle/types";
import type { LifecycleGate } from "@/lib/agent-lifecycle/types";

interface PromotionPathProps {
  steps: MainStepDisplay[];
  gates: (LifecycleGate | null)[];
}

export function PromotionPath({ steps, gates }: PromotionPathProps) {
  return (
    <div className="promotion">
      <div className="promotion__head">
        <h3 className="section-title">Promotion path</h3>
      </div>

      <div className="promopath">
        {steps.map((step, i) => {
          const isDone = step.state === "done";
          const isCurrent = step.state === "current";
          const gate = i > 0 ? gates[i - 1] : null;

          return (
            <div key={step.step} style={{ display: "contents" }}>
              {/* Gate connector (between steps) */}
              {i > 0 && (
                <div className="promopath__connector">
                  <div className={`promopath__line${isDone ? " promopath__line--done" : ""}`} />
                  {gate && (
                    <span className="promopath__gate">{gate.title}</span>
                  )}
                </div>
              )}

              {/* Step node */}
              <div className="promopath__step">
                <div
                  className={
                    isDone
                      ? "promopath__dot promopath__dot--done"
                      : isCurrent
                      ? "promopath__dot promopath__dot--current"
                      : "promopath__dot promopath__dot--locked"
                  }
                >
                  {isDone && <Check size={10} strokeWidth={3} />}
                  {!isDone && !isCurrent && <Lock size={8} />}
                </div>
                <span
                  className={`promopath__label promopath__label--${isDone ? "done" : isCurrent ? "current" : "locked"}`}
                >
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
