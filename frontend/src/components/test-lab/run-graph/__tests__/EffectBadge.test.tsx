import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

// Isolated component - mirrors what will be in RunGraph
function EffectDenialBadge({ effects }: { effects: string[] }) {
  if (!effects.length) return null;
  return (
    <span
      className="text-ork-red bg-ork-red-bg"
      title={`effects [${effects.join(", ")}] are forbidden for this agent`}
    >
      ⛔ blocked: {effects.join(", ")}
    </span>
  );
}

describe("EffectDenialBadge", () => {
  it("renders blocked effects", () => {
    render(<EffectDenialBadge effects={["write"]} />);
    expect(screen.getByText(/blocked: write/)).toBeTruthy();
  });

  it("renders compound effects", () => {
    render(<EffectDenialBadge effects={["write", "act"]} />);
    expect(screen.getByText(/blocked: write, act/)).toBeTruthy();
  });

  it("renders nothing for empty effects", () => {
    const { container } = render(<EffectDenialBadge effects={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
