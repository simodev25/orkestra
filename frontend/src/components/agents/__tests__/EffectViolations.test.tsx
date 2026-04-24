import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";

interface Violation {
  id: string;
  run_id: string;
  mcp_id: string;
  effects: string[];
  blocked_at: string | null;
}

function EffectViolationsSection({
  violations,
  summary,
  isEditMode,
}: {
  violations: Violation[];
  summary: Record<string, number>;
  isEditMode: boolean;
}) {
  if (!isEditMode) return null;
  return (
    <section data-testid="effect-violations">
      <h3>Violations d&apos;effet</h3>
      <div data-testid="summary">
        {Object.entries(summary).map(([effect, count]) => (
          <span key={effect} data-testid={`summary-${effect}`}>
            {effect}: {count}
          </span>
        ))}
      </div>
      {violations.length === 0 ? (
        <p data-testid="no-violations">Aucune violation</p>
      ) : (
        <table>
          <tbody>
            {violations.map((v) => (
              <tr key={v.id} data-testid={`violation-${v.id}`}>
                <td>{v.run_id}</td>
                <td>{v.mcp_id}</td>
                <td>{v.effects.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

describe("EffectViolationsSection", () => {
  it("is hidden in create mode", () => {
    const { container } = render(
      <EffectViolationsSection violations={[]} summary={{}} isEditMode={false} />
    );
    expect(container.firstChild).toBeNull();
  });

  it("shows no-violations message when empty", () => {
    render(<EffectViolationsSection violations={[]} summary={{}} isEditMode={true} />);
    expect(screen.getByTestId("no-violations")).toBeTruthy();
  });

  it("renders violation rows", () => {
    const violations = [
      { id: "v1", run_id: "run_abc", mcp_id: "fs_mcp", effects: ["write"], blocked_at: null },
    ];
    render(<EffectViolationsSection violations={violations} summary={{ write: 1 }} isEditMode={true} />);
    expect(screen.getByTestId("violation-v1")).toBeTruthy();
    expect(screen.getByTestId("summary-write").textContent).toBe("write: 1");
  });

  it("renders summary badges", () => {
    render(
      <EffectViolationsSection
        violations={[]}
        summary={{ write: 5, act: 2 }}
        isEditMode={true}
      />
    );
    expect(screen.getByTestId("summary-write").textContent).toBe("write: 5");
    expect(screen.getByTestId("summary-act").textContent).toBe("act: 2");
  });
});
