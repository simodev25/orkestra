"use client";

import { AnimatePresence, motion } from 'framer-motion';
import { X, AlertTriangle } from 'lucide-react';
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
};

export function DetailPanel({ node, onClose }: DetailPanelProps) {
  return (
    <AnimatePresence>
      {node && (
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
          {/* Panel header */}
          <div className="flex items-start gap-3 p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
            <div
              className="flex items-center justify-center rounded-xl flex-shrink-0"
              style={{
                width: 46, height: 46,
                background: `rgba(0,0,0,0.3)`,
                border: `1px solid ${node.color}33`,
              }}
            >
              <NodeIcon name={node.iconName} size={22} color={node.color} strokeWidth={1.6} />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[8px] font-bold tracking-[0.14em] uppercase opacity-45" style={{ color: node.color }}>
                {node.kind.toUpperCase()} · AGENT
              </p>
              <p className="text-[14px] font-bold truncate" style={{ color: node.color }}>
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

          {/* Stats */}
          <div className="grid grid-cols-3 gap-2 p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.05)' }}>
            {[
              { label: 'DURÉE',  value: fmt(node.durationMs), color: node.color },
              { label: 'STATUS', value: node.status,          color: node.status === 'completed' ? '#10b981' : node.status === 'failed' ? '#ef4444' : '#f59e0b' },
              { label: 'EVENTS', value: String(node.events.length), color: '#71717a' },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-xl p-2.5" style={{ background: '#0d0d18', border: '1px solid #1a1a28' }}>
                <p className="text-[7px] font-bold tracking-[0.1em] mb-1.5" style={{ color: '#3f3f5a' }}>{label}</p>
                <p className="text-[13px] font-bold font-mono" style={{ color }}>{value}</p>
              </div>
            ))}
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto" style={{ scrollbarWidth: 'thin', scrollbarColor: '#1e1e2e transparent' }}>

            {/* Final output (runtime only) */}
            {node.output != null && (
              <div className="p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                <p className="text-[8px] font-bold tracking-[0.12em] uppercase mb-2" style={{ color: '#3f3f5a' }}>
                  SORTIE FINALE
                </p>
                <pre
                  className="rounded-xl p-3 text-[10px] font-mono leading-relaxed overflow-x-auto"
                  style={{ background: '#080812', border: '1px solid #1a1a26', color: '#71717a' }}
                >
                  {JSON.stringify(node.output, null, 2)}
                </pre>
              </div>
            )}

            {/* Events */}
            {node.events.length > 0 && (
              <div className="p-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.04)' }}>
                <p className="text-[8px] font-bold tracking-[0.12em] uppercase mb-2" style={{ color: '#3f3f5a' }}>
                  ÉVÉNEMENTS ({node.events.length})
                </p>
                <div className="flex flex-col gap-1.5">
                  {node.events.slice(0, 10).map((ev, i) => (
                    <div
                      key={`${ev.id}-${i}`}
                      className="flex items-start gap-2 rounded-lg p-2"
                      style={{ background: '#0d0d18', border: '1px solid #1a1a28' }}
                    >
                      <span
                        className="text-[7px] font-bold rounded px-1.5 py-0.5 flex-shrink-0 mt-0.5"
                        style={{
                          background: EVENT_BADGE[ev.event_type] ?? 'rgba(255,255,255,0.05)',
                          color: EVENT_TEXT[ev.event_type] ?? '#71717a',
                        }}
                      >
                        {ev.event_type.replace(/_/g, ' ').toUpperCase()}
                      </span>
                      <div className="min-w-0">
                        <p className="text-[9px] font-mono" style={{ color: '#3f3f5a' }}>{fmtTime(ev.timestamp)}</p>
                        {ev.message && (
                          <p className="text-[10px] mt-0.5 leading-snug truncate" style={{ color: '#71717a' }}>
                            {ev.message.slice(0, 80)}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                  {node.events.length > 10 && (
                    <p className="text-[9px] font-mono text-center" style={{ color: '#3f3f5a' }}>
                      +{node.events.length - 10} more
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Diagnostics */}
            {node.diagnostics.length > 0 && (
              <div className="p-4">
                <p className="text-[8px] font-bold tracking-[0.12em] uppercase mb-2" style={{ color: '#3f3f5a' }}>
                  DIAGNOSTICS ({node.diagnostics.length})
                </p>
                <div className="flex flex-col gap-2">
                  {node.diagnostics.map((d) => (
                    <div
                      key={d.id}
                      className="rounded-xl p-3"
                      style={{ background: 'rgba(245,158,11,0.06)', border: '1px solid rgba(245,158,11,0.18)' }}
                    >
                      <div className="flex items-center gap-1.5 mb-1">
                        <AlertTriangle size={11} color="#f59e0b" />
                        <span className="text-[10px] font-bold" style={{ color: '#f59e0b' }}>{d.code}</span>
                      </div>
                      <p className="text-[10px] leading-relaxed" style={{ color: '#71717a' }}>{d.message}</p>
                      {d.recommendation && (
                        <p className="text-[9px] mt-1.5 font-mono" style={{ color: '#52525b' }}>
                          → {d.recommendation}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
