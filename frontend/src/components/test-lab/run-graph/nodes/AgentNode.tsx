"use client";

import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { motion } from 'framer-motion';
import { CheckCircle, XCircle } from 'lucide-react';
import type { AgentNodeData } from '@/lib/test-lab/graph-types';
import { NodeIcon } from '../NodeIcon';

type AgentNodeType = Node<AgentNodeData, 'agentNode'>;

const hexToRgba = (hex: string, alpha: number) => {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
};

const PHASE_TAG: Record<string, string> = {
  preparation: 'AGENT · PREP',
  runtime:     'RUNTIME · AGENT',
  assertions:  'AGENT · ASSERT',
  diagnostics: 'AGENT · DIAG',
  report:      'JUDGE · REPORT',
};

export const AgentNode = memo(function AgentNode({
  data,
  selected,
}: NodeProps<AgentNodeType>) {
  const { kind, label, subLabel, iconName, color, status, durationMs, visible, verdict, score } = data;

  const isRunning  = status === 'running';
  const isFailed   = status === 'failed';
  const isReport   = kind === 'report';
  const accentColor = isFailed ? '#ef4444' : color;

  // Status color using CSS vars where possible, fallback to hex for dynamic checks
  const statusColor =
    status === 'completed' ? 'var(--ork-green)' :
    status === 'failed'    ? 'var(--ork-red)' :
    status === 'warning'   ? 'var(--ork-amber)' :
    'var(--ork-purple)';

  const durationLabel =
    durationMs != null
      ? durationMs >= 1000 ? `${(durationMs / 1000).toFixed(1)}s` : `${durationMs}ms`
      : null;

  const phaseTag = PHASE_TAG[kind] ?? 'AGENT';

  // ── Verdict display (report node) ───────────────────────────────────────────
  const verdictPassed = verdict === 'passed' || verdict === 'passed_with_warnings';
  // verdictColor stays as hex since it feeds into hexToRgba()
  const verdictColorHex  =
    verdict === 'passed'               ? '#10b981' :
    verdict === 'passed_with_warnings' ? '#f59e0b' :
    verdict === 'failed'               ? '#ef4444' :
    color;

  const effectiveAccent = isReport && verdict ? verdictColorHex : accentColor;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85, y: 12 }}
      animate={visible
        ? { opacity: 1, scale: 1, y: 0 }
        : { opacity: 0, scale: 0.85, y: 12 }
      }
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
    >
      {/* Running pulse ring */}
      {isRunning && visible && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            border: `1px solid ${color}`,
            boxShadow: `0 0 14px ${color}55`,
            borderRadius: 'var(--radius-lg)',
            animation: 'nodeRingPulse 1.4s ease-in-out infinite',
          }}
        />
      )}

      <div
        className="relative overflow-hidden"
        style={{
          width: 210,
          background: hexToRgba(effectiveAccent, isReport && verdict ? 0.07 : 0.05),
          border: `1px solid ${
            selected
              ? 'var(--ork-cyan)'
              : isRunning ? `${color}99`
              : hexToRgba(effectiveAccent, 0.25)
          }`,
          borderRadius: 'var(--radius-lg)',
          boxShadow: selected
            ? '0 0 0 2px var(--ork-cyan), 0 16px 48px color-mix(in oklch, var(--ork-cyan) 18%, transparent)'
            : isReport && verdict
              ? `0 8px 32px ${verdictColorHex}22`
              : isRunning
                ? `0 8px 32px ${color}22`
                : '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        {/* Top shimmer */}
        <div
          className="absolute top-0 inset-x-8 h-px"
          style={{ background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)' }}
        />

        {/* Header */}
        <div className="flex items-center gap-2 px-3 pt-3 pb-2">
          <div
            className="flex items-center justify-center flex-shrink-0"
            style={{
              width: 36, height: 36,
              background: hexToRgba(effectiveAccent, 0.12),
              borderRadius: 'var(--radius)',
            }}
          >
            <NodeIcon
              name={iconName}
              size={18}
              color={effectiveAccent}
              strokeWidth={1.8}
            />
          </div>
          <div className="min-w-0 flex-1">
            <p
              className="chip chip--mini"
              style={{
                background: hexToRgba(effectiveAccent, 0.08),
                borderColor: hexToRgba(effectiveAccent, 0.2),
                color: effectiveAccent,
                marginBottom: 2,
                display: 'inline-flex',
              }}
            >
              {phaseTag}
            </p>
            <p
              style={{
                fontSize: 12,
                fontWeight: 700,
                color: effectiveAccent,
                lineHeight: 1.3,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                margin: 0,
              }}
            >
              {label}
            </p>
            <p
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: 'var(--ork-muted-2)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                margin: 0,
              }}
            >
              {subLabel}
            </p>
          </div>
        </div>

        {/* Report verdict row */}
        {isReport && verdict && (
          <div className="flex items-center gap-2 px-3 pb-2">
            {verdictPassed
              ? <CheckCircle size={13} color={verdictColorHex} />
              : <XCircle    size={13} color={verdictColorHex} />
            }
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                fontFamily: 'var(--font-mono)',
                color: verdictColorHex,
              }}
            >
              {verdict === 'passed_with_warnings' ? 'PASSED ⚠' : verdict?.toUpperCase()}
              {score != null && ` · ${score.toFixed(0)}/100`}
            </span>
          </div>
        )}

        {/* Footer */}
        <div
          className="flex items-center gap-1"
          style={{
            padding: '5px 12px',
            borderTop: '1px solid var(--ork-border)',
          }}
        >
          {isRunning ? (
            <div
              className="rounded-full flex-shrink-0"
              style={{ width: 5, height: 5, background: 'var(--ork-purple)', animation: 'dotBlink 0.8s ease-in-out infinite' }}
            />
          ) : (
            <div
              className="rounded-full flex-shrink-0"
              style={{ width: 5, height: 5, background: statusColor, boxShadow: `0 0 5px currentColor` }}
            />
          )}
          <span style={{ fontSize: 9, fontWeight: 600, color: statusColor }}>
            {status}
          </span>
          {durationLabel && (
            <span
              style={{
                marginLeft: 'auto',
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: 'var(--ork-muted-2)',
              }}
            >
              {durationLabel}
            </span>
          )}
        </div>

        <Handle
          type="target"
          position={Position.Left}
          style={{
            background: 'var(--ork-bg)',
            borderColor: hexToRgba(accentColor, 0.5),
            width: 10,
            height: 10,
          }}
        />
        <Handle
          type="source"
          position={Position.Right}
          style={{
            background: 'var(--ork-bg)',
            borderColor: hexToRgba(accentColor, 0.5),
            width: 10,
            height: 10,
          }}
        />
      </div>
    </motion.div>
  );
});
