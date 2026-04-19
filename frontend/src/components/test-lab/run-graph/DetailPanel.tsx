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

const EVENT_BADGE: Record<string, string> = {
  phase_started:             'rgba(0,212,255,0.12)',
  assertion_phase_started:   'rgba(0,212,255,0.12)',
  diagnostic_phase_started:  'rgba(0,212,255,0.12)',
  report_phase_started:      'rgba(0,212,255,0.12)',
  phase_completed:           'rgba(16,185,129,0.12)',
  iteration:                 'rgba(167,139,250,0.12)',
  agent_message:             'rgba(167,139,250,0.12)',
  diagnostic_generated:      'rgba(245,158,11,0.12)',
  orchestrator_tool_call:    'rgba(167,139,250,0.12)',
  pipeline_tool_call:        'rgba(56,189,248,0.12)',
  pipeline_agent_output:     'rgba(56,189,248,0.12)',
};
const EVENT_TEXT: Record<string, string> = {
  phase_started:             '#00d4ff',
  assertion_phase_started:   '#00d4ff',
  diagnostic_phase_started:  '#00d4ff',
  report_phase_started:      '#00d4ff',
  phase_completed:           '#10b981',
  iteration:                 '#a78bfa',
  agent_message:             '#a78bfa',
  diagnostic_generated:      '#f59e0b',
  orchestrator_tool_call:    '#a78bfa',
  pipeline_tool_call:        '#38bdf8',
  pipeline_agent_output:     '#38bdf8',
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
    node.verdict === 'passed'               ? '#10b981' :
    node.verdict === 'passed_with_warnings' ? '#f59e0b' :
    node.verdict === 'failed'               ? '#ef4444' :
    node.color;
  const panelAccent = isReport && node.verdict ? verdictColor : node.color;

  // iteration count from events
  const iterCount = node.events.filter(e => e.event_type === 'iteration' || e.event_type === 'agent_message').length;

  return (
    <AnimatePresence>
      <motion.div
        key="detail-panel"
        initial={{ x: 40, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 40, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        className="flex flex-col border-l"
        style={{
          width: 320,
          flexShrink: 0,
          background: 'rgba(9,9,18,0.98)',
          borderColor: 'rgba(255,255,255,0.06)',
        }}
      >
        {/* ── Panel header ─────────────────────────────────────────────── */}
        <div className="flex items-start gap-3 p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
          <div
            className="flex items-center justify-center rounded-xl flex-shrink-0"
            style={{
              width: 46, height: 46,
              background: `rgba(0,0,0,0.3)`,
              border: `1px solid ${panelAccent}33`,
            }}
          >
            <NodeIcon name={node.iconName} size={22} color={panelAccent} strokeWidth={1.6} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-[8px] font-bold tracking-[0.14em] uppercase opacity-45" style={{ color: panelAccent }}>
              {getPhaseTag(node.kind)}
            </p>
            <p className="text-[14px] font-bold truncate" style={{ color: panelAccent }}>
              {node.label}
            </p>
            <p className="text-[10px] font-mono opacity-35 truncate">{node.subLabel}</p>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 transition-colors hover:bg-white/5 text-ork-muted hover:text-ork-text flex-shrink-0"
          >
            <X size={14} />
          </button>
        </div>

        {/* ── Verdict banner (report node) ─────────────────────────────── */}
        {isReport && node.verdict && (
          <div
            className="flex items-center gap-2.5 px-4 py-3 border-b"
            style={{
              borderColor: `${verdictColor}22`,
              background: `${verdictColor}0d`,
            }}
          >
            {node.verdict === 'failed'
              ? <XCircle size={18} color={verdictColor} />
              : <CheckCircle size={18} color={verdictColor} />
            }
            <div>
              <p className="text-[13px] font-bold font-mono" style={{ color: verdictColor }}>
                {node.verdict === 'passed_with_warnings' ? 'PASSED WITH WARNINGS' : node.verdict?.toUpperCase()}
              </p>
              {node.score != null && (
                <p className="text-[10px] font-mono opacity-60" style={{ color: verdictColor }}>
                  Score : {node.score.toFixed(0)}/100
                </p>
              )}
            </div>
          </div>
        )}

        {/* ── Stats ────────────────────────────────────────────────────── */}
        <div className="grid grid-cols-3 gap-2 p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
          {[
            { label: 'DURÉE',  value: fmt(node.durationMs),        color: panelAccent },
            { label: 'STATUS', value: node.status,                  color: node.status === 'completed' ? '#10b981' : node.status === 'failed' ? '#ef4444' : '#f59e0b' },
            { label: node.kind === 'runtime' ? 'ITERS' : 'EVENTS', value: node.kind === 'runtime' ? String(iterCount || node.events.length) : String(node.events.length), color: '#71717a' },
          ].map(({ label, value, color }) => (
            <div key={label} className="rounded-xl p-2.5" style={{ background: '#0d0d18', border: '1px solid #1a1a28' }}>
              <p className="text-[7px] font-bold tracking-[0.1em] mb-1.5" style={{ color: '#3f3f5a' }}>{label}</p>
              <p className="text-[13px] font-bold font-mono truncate" style={{ color }}>{value}</p>
            </div>
          ))}
        </div>

        {/* ── Scrollable body ──────────────────────────────────────────── */}
        <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin', scrollbarColor: '#1e1e2e transparent' }}>

          {/* SORTIE FINALE */}
          {node.output != null && (
            <div className="p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
              <p className="text-[8px] font-bold tracking-[0.12em] uppercase mb-2" style={{ color: panelAccent }}>
                SORTIE FINALE
              </p>
              <pre
                className="rounded-xl p-3 text-[10px] font-mono leading-relaxed overflow-x-auto max-h-[260px] overflow-y-auto"
                style={{ background: '#080812', border: '1px solid #1a1a26', color: '#71717a' }}
              >
                {typeof node.output === 'string' ? node.output : JSON.stringify(node.output, null, 2)}
              </pre>
            </div>
          )}

          {/* Diagnostics */}
          {node.diagnostics.length > 0 && (
            <div className="p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
              <div className="flex items-center gap-1.5 mb-2">
                <AlertTriangle size={9} color="#f59e0b" />
                <p className="text-[8px] font-bold tracking-[0.12em] uppercase" style={{ color: '#f59e0b' }}>
                  Diagnostics <span style={{ color: '#3f3f5a' }}>({node.diagnostics.length})</span>
                </p>
              </div>
              <div className="flex flex-col gap-1.5">
                {node.diagnostics.map((d) => {
                  const sevColor =
                    d.severity === 'critical' || d.severity === 'error' ? '#ef4444' :
                    d.severity === 'warning' ? '#f59e0b' : '#10b981';
                  return (
                    <div
                      key={d.id}
                      className="rounded-lg p-3"
                      style={{ background: `${sevColor}08`, border: `1px solid ${sevColor}22` }}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <div style={{ width: 6, height: 6, borderRadius: '50%', background: sevColor, flexShrink: 0, boxShadow: `0 0 5px ${sevColor}` }} />
                        <span className="text-[10px] font-bold font-mono" style={{ color: sevColor }}>{d.code}</span>
                      </div>
                      <p className="text-[9px] leading-relaxed" style={{ color: '#71717a' }}>{d.message}</p>
                      {d.recommendation && (
                        <p className="text-[9px] mt-1.5 font-mono" style={{ color: '#52525b' }}>
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
              <div className="flex items-center gap-1.5 mb-2">
                <Clock size={9} color="#52525b" />
                <p className="text-[8px] font-bold tracking-[0.12em] uppercase" style={{ color: '#52525b' }}>
                  Log <span style={{ color: '#3f3f5a' }}>({node.events.length})</span>
                </p>
              </div>
              <div className="flex flex-col gap-0">
                {node.events.slice(0, 14).map((ev, i) => {
                  const dotColor = EVENT_TEXT[ev.event_type] ?? '#3f3f5a';
                  return (
                    <div
                      key={`${ev.id}-${i}`}
                      className="flex items-start gap-2 py-1.5"
                      style={{ borderTop: i > 0 ? '1px solid rgba(255,255,255,0.03)' : 'none' }}
                    >
                      {/* colored dot */}
                      <div className="flex-shrink-0 mt-[5px]"
                        style={{ width: 5, height: 5, borderRadius: '50%', background: dotColor, boxShadow: `0 0 4px ${dotColor}88` }}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-1.5">
                          <span className="text-[9px] font-bold capitalize flex-shrink-0" style={{ color: dotColor }}>
                            {ev.event_type.replace(/_/g, ' ')}
                          </span>
                          <span className="text-[9px] font-mono flex-shrink-0" style={{ color: '#2d2d40' }}>
                            {fmtTime(ev.timestamp)}
                          </span>
                        </div>
                        {ev.message && (
                          <p className="text-[9px] leading-snug truncate" style={{ color: '#52525b' }}>
                            {ev.message.slice(0, 80)}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
                {node.events.length > 14 && (
                  <p className="text-[9px] font-mono mt-1" style={{ color: '#2d2d40' }}>
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
