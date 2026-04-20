"use client";

import { AnimatePresence, motion } from 'framer-motion';
import { X, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react';
import type { AgentNodeData } from '@/lib/test-lab/graph-types';
import { NodeIcon } from './NodeIcon';

interface DetailPanelProps {
  node: AgentNodeData | null;
  onClose: () => void;
}

function fmt(ms: number | null | undefined): string {
  if (ms == null) return '--';
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}

function fmtTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', {
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });
}

const EVENT_TEXT: Record<string, string> = {
  phase_started:             'var(--ork-cyan)',
  assertion_phase_started:   'var(--ork-cyan)',
  diagnostic_phase_started:  'var(--ork-cyan)',
  report_phase_started:      'var(--ork-cyan)',
  phase_completed:           'var(--ork-green)',
  iteration:                 'var(--ork-purple)',
  agent_message:             'var(--ork-purple)',
  diagnostic_generated:      'var(--ork-amber)',
  orchestrator_tool_call:    'var(--ork-purple)',
  pipeline_tool_call:        'var(--ork-cyan)',
  pipeline_agent_output:     'var(--ork-cyan)',
};

const PHASE_TAG: Record<string, string> = {
  orchestrator: 'ORCHESTRATOR',
  preparation:  'AGENT · PREP',
  runtime:      'RUNTIME · AGENT',
  assertions:   'AGENT · ASSERT',
  diagnostics:  'AGENT · DIAG',
  report:       'JUDGE · REPORT',
};

function getPhaseTag(kind: string): string {
  if (PHASE_TAG[kind]) return PHASE_TAG[kind];
  if (kind.startsWith('pipeline_')) return 'PIPELINE · AGENT';
  return kind.toUpperCase();
}

export function DetailPanel({ node, onClose }: DetailPanelProps) {
  if (!node) return null;

  const isReport = node.kind === 'report';
  const verdictColor =
    node.verdict === 'passed'               ? 'var(--ork-green)' :
    node.verdict === 'passed_with_warnings' ? 'var(--ork-amber)' :
    node.verdict === 'failed'               ? 'var(--ork-red)' :
    node.color;
  const panelAccent = isReport && node.verdict ? verdictColor : node.color;

  // iteration count from events
  const iterCount = node.events.filter(e => e.event_type === 'iteration' || e.event_type === 'agent_message').length;

  // Status color via CSS vars
  const statusColor =
    node.status === 'completed' ? 'var(--ork-green)' :
    node.status === 'failed'    ? 'var(--ork-red)' :
    'var(--ork-amber)';

  return (
    <AnimatePresence>
      <motion.div
        key="detail-panel"
        initial={{ x: 40, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 40, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        className="detail flex flex-col"
        style={{
          width: 320,
          flexShrink: 0,
          borderRadius: 0,
          borderTop: 'none',
          borderBottom: 'none',
          borderRight: 'none',
          maxHeight: '100%',
          position: 'relative',
          top: 'unset',
        }}
      >
        {/* ── Panel header ─────────────────────────────────────────────── */}
        <div
          className="flex items-start gap-3 p-4"
          style={{ borderBottom: '1px solid var(--ork-border)' }}
        >
          <div
            className="flex items-center justify-center flex-shrink-0"
            style={{
              width: 46, height: 46,
              background: 'var(--ork-surface)',
              border: `1px solid color-mix(in oklch, ${panelAccent} 20%, transparent)`,
              borderRadius: 'var(--radius-lg)',
            }}
          >
            <NodeIcon name={node.iconName} size={22} color={panelAccent} strokeWidth={1.6} />
          </div>
          <div className="flex-1 min-w-0">
            <p
              className="section-title"
              style={{ color: panelAccent, marginBottom: 2 }}
            >
              {getPhaseTag(node.kind)}
            </p>
            <p className="detail__name" style={{ color: panelAccent, fontSize: 14, margin: 0 }}>
              {node.label}
            </p>
            <p className="detail__id">{node.subLabel}</p>
          </div>
          <button
            onClick={onClose}
            className="btn btn--ghost"
            style={{ padding: '4px 6px', height: 'auto' }}
          >
            <X size={14} />
          </button>
        </div>

        {/* ── Verdict banner (report node) ─────────────────────────────── */}
        {isReport && node.verdict && (
          <div
            className="flex items-center gap-2 px-4 py-3"
            style={{
              borderBottom: `1px solid color-mix(in oklch, ${verdictColor} 15%, transparent)`,
              background: `color-mix(in oklch, ${verdictColor} 6%, transparent)`,
            }}
          >
            {node.verdict === 'failed'
              ? <XCircle size={18} style={{ color: verdictColor }} />
              : <CheckCircle size={18} style={{ color: verdictColor }} />
            }
            <div>
              <p
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 13,
                  fontWeight: 700,
                  color: verdictColor,
                  margin: 0,
                }}
              >
                {node.verdict === 'passed_with_warnings' ? 'PASSED WITH WARNINGS' : node.verdict?.toUpperCase()}
              </p>
              {node.score != null && (
                <p
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    color: verdictColor,
                    opacity: 0.6,
                    margin: 0,
                  }}
                >
                  Score : {node.score.toFixed(0)}/100
                </p>
              )}
            </div>
          </div>
        )}

        {/* ── Stats ────────────────────────────────────────────────────── */}
        <div className="p-4" style={{ borderBottom: '1px solid var(--ork-border)' }}>
          <div className="kv">
            <span className="k">DURÉE</span>
            <span className="v mono" style={{ color: panelAccent }}>{fmt(node.durationMs)}</span>
            <span className="k">STATUS</span>
            <span className="v mono" style={{ color: statusColor }}>{node.status}</span>
            <span className="k">{node.kind === 'runtime' ? 'ITERS' : 'EVENTS'}</span>
            <span className="v mono">
              {node.kind === 'runtime' ? String(iterCount || node.events.length) : String(node.events.length)}
            </span>
          </div>
        </div>

        {/* ── Scrollable body ──────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin' }}>

          {/* SORTIE FINALE */}
          {node.output != null && (
            <div className="p-4" style={{ borderBottom: '1px solid var(--ork-border)' }}>
              <p className="section-title" style={{ color: panelAccent, marginBottom: 6 }}>
                SORTIE FINALE
              </p>
              <pre className="codebox" style={{ fontSize: 10, maxHeight: 260 }}>
                {typeof node.output === 'string' ? node.output : JSON.stringify(node.output, null, 2)}
              </pre>
            </div>
          )}

          {/* Diagnostics */}
          {node.diagnostics.length > 0 && (
            <div className="p-4" style={{ borderBottom: '1px solid var(--ork-border)' }}>
              <div className="flex items-center gap-1" style={{ marginBottom: 8 }}>
                <AlertTriangle size={9} style={{ color: 'var(--ork-amber)' }} />
                <p className="section-title" style={{ color: 'var(--ork-amber)', margin: 0 }}>
                  Diagnostics <span style={{ color: 'var(--ork-muted-2)' }}>({node.diagnostics.length})</span>
                </p>
              </div>
              <div className="flex flex-col gap-1">
                {node.diagnostics.map((d) => {
                  const sevColor =
                    d.severity === 'critical' || d.severity === 'error' ? 'var(--ork-red)' :
                    d.severity === 'warning' ? 'var(--ork-amber)' : 'var(--ork-green)';
                  return (
                    <div
                      key={d.id}
                      style={{
                        background: `color-mix(in oklch, ${sevColor} 6%, transparent)`,
                        border: `1px solid color-mix(in oklch, ${sevColor} 20%, transparent)`,
                        borderRadius: 'var(--radius)',
                        padding: '8px 10px',
                      }}
                    >
                      <div className="flex items-center gap-1" style={{ marginBottom: 4 }}>
                        <div className="glow-dot" style={{ color: sevColor, width: 5, height: 5 }} />
                        <span
                          style={{
                            fontFamily: 'var(--font-mono)',
                            fontSize: 10,
                            fontWeight: 700,
                            color: sevColor,
                          }}
                        >
                          {d.code}
                        </span>
                      </div>
                      <p style={{ fontSize: 9, color: 'var(--ork-muted)', margin: 0, lineHeight: 1.5 }}>
                        {d.message}
                      </p>
                      {d.recommendation && (
                        <p
                          style={{
                            fontSize: 9,
                            fontFamily: 'var(--font-mono)',
                            color: 'var(--ork-muted-2)',
                            marginTop: 4,
                            marginBottom: 0,
                          }}
                        >
                          → {d.recommendation}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Events — compact single-line rows */}
          {node.events.length > 0 && (
            <div className="p-4">
              <div className="flex items-center gap-1" style={{ marginBottom: 8 }}>
                <Clock size={9} style={{ color: 'var(--ork-muted-2)' }} />
                <p className="section-title" style={{ margin: 0 }}>
                  Log <span style={{ color: 'var(--ork-muted-2)' }}>({node.events.length})</span>
                </p>
              </div>
              <div className="flex flex-col gap-0">
                {node.events.slice(0, 14).map((ev, i) => {
                  const dotColor = EVENT_TEXT[ev.event_type] ?? 'var(--ork-muted-2)';
                  return (
                    <div
                      key={`${ev.id}-${i}`}
                      className="flex items-start gap-2 py-1"
                      style={{ borderTop: i > 0 ? '1px solid var(--ork-border)' : 'none' }}
                    >
                      {/* colored dot */}
                      <div
                        className="flex-shrink-0"
                        style={{
                          width: 5, height: 5,
                          borderRadius: '50%',
                          background: dotColor,
                          boxShadow: `0 0 4px color-mix(in oklch, ${dotColor} 60%, transparent)`,
                          marginTop: 5,
                        }}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-1">
                          <span
                            style={{
                              fontSize: 9,
                              fontWeight: 700,
                              color: dotColor,
                              textTransform: 'capitalize',
                              flexShrink: 0,
                            }}
                          >
                            {ev.event_type.replace(/_/g, ' ')}
                          </span>
                          <span
                            style={{
                              fontSize: 9,
                              fontFamily: 'var(--font-mono)',
                              color: 'var(--ork-border-2)',
                              flexShrink: 0,
                            }}
                          >
                            {fmtTime(ev.timestamp)}
                          </span>
                        </div>
                        {ev.message && (
                          <p
                            style={{
                              fontSize: 9,
                              color: 'var(--ork-muted-2)',
                              margin: 0,
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {ev.message.slice(0, 80)}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
                {node.events.length > 14 && (
                  <p
                    style={{
                      fontSize: 9,
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--ork-border-2)',
                      marginTop: 4,
                    }}
                  >
                    +{node.events.length - 14} more
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
