"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/status-badge";

interface ValidationFinding {
  rule_id: string;
  category: string;
  severity: string;
  message: string;
  field: string | null;
  suggestion: string | null;
}

interface ValidationReport {
  mcp_id: string;
  valid: boolean;
  score: number;
  errors: number;
  warnings: number;
  infos: number;
  categories_checked: string[];
  integration_tested: boolean;
  integration_latency_ms: number | null;
  findings: ValidationFinding[];
}

const SEVERITY_STYLES: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  error: { bg: "bg-ork-red/10", border: "border-ork-red/30", text: "text-ork-red", icon: "X" },
  warning: { bg: "bg-ork-amber/10", border: "border-ork-amber/30", text: "text-ork-amber", icon: "!" },
  info: { bg: "bg-ork-cyan/10", border: "border-ork-cyan/20", text: "text-ork-cyan", icon: "i" },
};

const CATEGORY_LABELS: Record<string, { label: string; description: string }> = {
  structural: { label: "Structural", description: "Required fields, format, identity" },
  governance: { label: "Governance", description: "Effect type, approval, audit, agent access" },
  runtime: { label: "Runtime", description: "Timeout, retry, cost configuration" },
  contract: { label: "Contract", description: "Input/output schema references" },
  integration: { label: "Integration", description: "Live test invocation" },
};

export default function McpValidatePage() {
  const params = useParams();
  const id = params.id as string;

  const [mcpName, setMcpName] = useState("");
  const [report, setReport] = useState<ValidationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [includeIntegration, setIncludeIntegration] = useState(true);
  const [gateTarget, setGateTarget] = useState<string | null>(null);
  const [gateReport, setGateReport] = useState<ValidationReport | null>(null);
  const [gateLoading, setGateLoading] = useState(false);

  useEffect(() => {
    fetch(`/api/mcps/${id}`)
      .then((r) => r.json())
      .then((d) => setMcpName(d.name || id))
      .catch(() => setMcpName(id));
  }, [id]);

  async function runValidation() {
    setLoading(true);
    setReport(null);
    try {
      const res = await fetch(`/api/mcps/${id}/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ include_integration: includeIntegration }),
      });
      const data = await res.json();
      setReport(data);
    } catch (e) {
      setReport({
        mcp_id: id, valid: false, score: 0, errors: 1, warnings: 0, infos: 0,
        categories_checked: [], integration_tested: false, integration_latency_ms: null,
        findings: [{ rule_id: "CLIENT_ERR", category: "structural", severity: "error",
          message: "Failed to reach validation API", field: null, suggestion: "Check backend connection" }],
      });
    }
    setLoading(false);
  }

  async function runGateCheck(target: string) {
    setGateTarget(target);
    setGateLoading(true);
    setGateReport(null);
    try {
      const res = await fetch(`/api/mcps/${id}/validate-gate/${target}`, { method: "POST" });
      const data = await res.json();
      setGateReport(data);
    } catch {
      setGateReport(null);
    }
    setGateLoading(false);
  }

  const scoreColor = !report ? "text-ork-muted"
    : report.score >= 80 ? "text-ork-green"
    : report.score >= 50 ? "text-ork-amber"
    : "text-ork-red";

  const groupedFindings: Record<string, ValidationFinding[]> = {};
  if (report) {
    for (const f of report.findings) {
      if (!groupedFindings[f.category]) groupedFindings[f.category] = [];
      groupedFindings[f.category].push(f);
    }
  }

  return (
    <div className="p-8 max-w-5xl animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <Link href={`/mcps/${id}`} className="text-xs font-mono text-ork-dim hover:text-ork-muted mb-2 block">
            &larr; BACK TO {mcpName.toUpperCase()}
          </Link>
          <h1 className="section-title text-lg">VALIDATE MCP</h1>
          <p className="text-ork-muted text-sm mt-1">
            Run validation rules against <span className="font-mono text-ork-cyan">{id}</span>
          </p>
        </div>
      </div>

      {/* Controls */}
      <div className="glass-panel p-5 mb-6">
        <div className="flex items-center gap-6">
          <button
            onClick={runValidation}
            disabled={loading}
            className="px-6 py-2.5 bg-ork-cyan/15 border border-ork-cyan/30 rounded-lg text-ork-cyan text-xs font-mono uppercase tracking-wider hover:bg-ork-cyan/25 disabled:opacity-40 transition-all"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="w-3 h-3 border border-ork-cyan/40 border-t-ork-cyan rounded-full animate-spin" />
                VALIDATING...
              </span>
            ) : (
              "RUN FULL VALIDATION"
            )}
          </button>

          <label className="flex items-center gap-2 text-sm text-ork-muted cursor-pointer">
            <input
              type="checkbox"
              checked={includeIntegration}
              onChange={(e) => setIncludeIntegration(e.target.checked)}
              className="w-4 h-4 rounded bg-ork-bg border-ork-border"
            />
            <span>Include integration test</span>
          </label>
        </div>

        {/* Lifecycle gates */}
        <div className="mt-4 pt-4 border-t border-ork-border">
          <p className="data-label mb-2">LIFECYCLE GATE CHECK</p>
          <div className="flex gap-2">
            {["tested", "registered", "active"].map((target) => (
              <button
                key={target}
                onClick={() => runGateCheck(target)}
                disabled={gateLoading}
                className={`px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider border rounded transition-colors ${
                  gateTarget === target
                    ? "bg-ork-purple/15 border-ork-purple/30 text-ork-purple"
                    : "border-ork-border text-ork-muted hover:border-ork-dim"
                }`}
              >
                Can transition to → {target}
              </button>
            ))}
          </div>
          {gateReport && gateTarget && (
            <div className={`mt-3 p-3 rounded border ${gateReport.valid ? "bg-ork-green/10 border-ork-green/30" : "bg-ork-red/10 border-ork-red/30"}`}>
              <p className={`text-sm font-mono ${gateReport.valid ? "text-ork-green" : "text-ork-red"}`}>
                {gateReport.valid
                  ? `✓ MCP can transition to "${gateTarget}" — all gate requirements met`
                  : `✗ MCP cannot transition to "${gateTarget}" — ${gateReport.errors} blocking issue(s)`}
              </p>
              {!gateReport.valid && gateReport.findings.length > 0 && (
                <ul className="mt-2 space-y-1">
                  {gateReport.findings.filter(f => f.severity === "error").map((f, i) => (
                    <li key={i} className="text-xs text-ork-red/80 font-mono pl-4">• {f.message}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Report */}
      {report && (
        <div className="space-y-6 animate-slide-up">
          {/* Score card */}
          <div className={`glass-panel p-6 border-l-4 ${report.valid ? "border-ork-green" : "border-ork-red"}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="data-label mb-1">VALIDATION SCORE</p>
                <p className={`text-5xl font-mono font-bold ${scoreColor}`}>{report.score}</p>
                <p className="text-xs text-ork-muted mt-1 font-mono">/ 100</p>
              </div>
              <div className="text-right">
                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-mono ${
                  report.valid ? "bg-ork-green/15 text-ork-green" : "bg-ork-red/15 text-ork-red"
                }`}>
                  <span className={`w-3 h-3 rounded-full ${report.valid ? "bg-ork-green" : "bg-ork-red"}`}
                    style={{ boxShadow: `0 0 8px ${report.valid ? "#10b981" : "#ef4444"}` }} />
                  {report.valid ? "VALID" : "INVALID"}
                </div>
                <div className="flex gap-4 mt-3">
                  <span className="text-xs font-mono text-ork-red">{report.errors} errors</span>
                  <span className="text-xs font-mono text-ork-amber">{report.warnings} warnings</span>
                  <span className="text-xs font-mono text-ork-cyan">{report.infos} info</span>
                </div>
              </div>
            </div>

            {/* Score bar */}
            <div className="mt-4 h-2 bg-ork-bg rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  report.score >= 80 ? "bg-ork-green" : report.score >= 50 ? "bg-ork-amber" : "bg-ork-red"
                }`}
                style={{ width: `${report.score}%` }}
              />
            </div>

            {/* Categories checked */}
            <div className="flex gap-2 mt-4">
              {report.categories_checked.map((cat) => {
                const catFindings = groupedFindings[cat] || [];
                const hasError = catFindings.some(f => f.severity === "error");
                const hasWarning = catFindings.some(f => f.severity === "warning");
                const color = hasError ? "border-ork-red/30 text-ork-red bg-ork-red/10"
                  : hasWarning ? "border-ork-amber/30 text-ork-amber bg-ork-amber/10"
                  : "border-ork-green/30 text-ork-green bg-ork-green/10";
                return (
                  <span key={cat} className={`px-2 py-0.5 text-[10px] font-mono uppercase border rounded ${color}`}>
                    {hasError ? "✗" : hasWarning ? "!" : "✓"} {cat}
                  </span>
                );
              })}
            </div>

            {report.integration_tested && report.integration_latency_ms !== null && (
              <p className="text-xs font-mono text-ork-muted mt-3">
                Integration test: {report.integration_latency_ms}ms
              </p>
            )}
          </div>

          {/* Findings by category */}
          {Object.entries(groupedFindings).map(([category, findings]) => {
            const catMeta = CATEGORY_LABELS[category] || { label: category, description: "" };
            return (
              <div key={category} className="glass-panel">
                <div className="px-5 py-3 border-b border-ork-border flex items-center justify-between">
                  <div>
                    <h3 className="section-title">{catMeta.label}</h3>
                    <p className="text-xs text-ork-dim mt-0.5">{catMeta.description}</p>
                  </div>
                  <span className="text-xs font-mono text-ork-muted">{findings.length} finding(s)</span>
                </div>
                <div className="divide-y divide-ork-border/50">
                  {findings.map((f, i) => {
                    const style = SEVERITY_STYLES[f.severity] || SEVERITY_STYLES.info;
                    return (
                      <div key={i} className={`px-5 py-4 ${style.bg}`}>
                        <div className="flex items-start gap-3">
                          <span className={`mt-0.5 w-5 h-5 rounded-full border flex items-center justify-center text-[10px] font-bold ${style.border} ${style.text}`}>
                            {style.icon}
                          </span>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className={`text-[10px] font-mono uppercase tracking-wider ${style.text}`}>
                                {f.severity}
                              </span>
                              <span className="text-[10px] font-mono text-ork-dim">{f.rule_id}</span>
                              {f.field && (
                                <span className="text-[10px] font-mono text-ork-muted px-1.5 py-0.5 bg-ork-bg rounded">
                                  {f.field}
                                </span>
                              )}
                            </div>
                            <p className="text-sm text-ork-text">{f.message}</p>
                            {f.suggestion && (
                              <p className="text-xs text-ork-muted mt-1.5 flex items-start gap-1.5">
                                <span className="text-ork-cyan">→</span>
                                {f.suggestion}
                              </p>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* All clear message */}
          {report.findings.length === 0 && (
            <div className="glass-panel p-8 text-center border-ork-green/20">
              <div className="w-12 h-12 rounded-full bg-ork-green/15 border border-ork-green/30 flex items-center justify-center mx-auto mb-3">
                <span className="text-ork-green text-xl">✓</span>
              </div>
              <p className="text-ork-green font-mono text-sm">ALL CHECKS PASSED</p>
              <p className="text-ork-muted text-xs mt-1">This MCP meets all validation rules</p>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!report && !loading && (
        <div className="glass-panel p-12 text-center">
          <p className="text-ork-muted text-sm mb-2">Click "Run Full Validation" to check this MCP</p>
          <p className="text-ork-dim text-xs font-mono">
            Validates structural, governance, runtime, contract, and integration rules
          </p>
        </div>
      )}
    </div>
  );
}
