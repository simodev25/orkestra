"use client";

import { usePathname } from "next/navigation";

const BREADCRUMB_LABELS: Record<string, string> = {
  agents: "agents",
  "test-lab": "test-lab",
  mcps: "mcps",
  runs: "runs",
  audit: "audit",
  approvals: "approvals",
  requests: "requests",
  cases: "cases",
  workflows: "workflows",
  plans: "plans",
  admin: "admin",
  control: "control",
};

export function Topbar() {
  const pathname = usePathname();

  const segments = pathname.split("/").filter(Boolean);
  const section = segments[0] ? BREADCRUMB_LABELS[segments[0]] || segments[0] : "dashboard";
  const sub = segments[1] && !segments[1].startsWith("[") ? segments[1] : null;

  return (
    <header className="topbar">
      <div className="topbar__crumbs">
        <span>orkestra</span>
        <span style={{ color: "var(--ork-border-2)" }}>/</span>
        <strong>{section}</strong>
        {sub && (
          <>
            <span style={{ color: "var(--ork-border-2)" }}>/</span>
            <span>{sub}</span>
          </>
        )}
      </div>
      <div className="topbar__right">
        <div className="topbar__health">
          <span className="glow-dot" style={{ color: "var(--ork-green)" }} />
          api · nominal
        </div>
      </div>
    </header>
  );
}
