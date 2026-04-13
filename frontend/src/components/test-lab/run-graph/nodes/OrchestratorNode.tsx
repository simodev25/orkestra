"use client";

import { memo } from 'react';
import { Handle, Position, type NodeProps, type Node } from '@xyflow/react';
import { motion } from 'framer-motion';
import type { AgentNodeData } from '@/lib/test-lab/graph-types';
import { NodeIcon } from '../NodeIcon';

type OrchestratorNodeType = Node<AgentNodeData, 'orchestratorNode'>;

export const OrchestratorNode = memo(function OrchestratorNode({
  data,
  selected,
}: NodeProps<OrchestratorNodeType>) {
  const { label, subLabel, iconName, color, status, durationMs, index } = data;

  const statusColor =
    status === 'completed' ? '#10b981' :
    status === 'failed'    ? '#ef4444' :
    status === 'warning'   ? '#f59e0b' :
    '#00d4ff'; // running

  const durationLabel =
    durationMs != null
      ? durationMs >= 1000
        ? `${(durationMs / 1000).toFixed(1)}s`
        : `${durationMs}ms`
      : null;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.85, y: 12 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28, delay: index * 0.08 }}
    >
      <div
        className="relative rounded-2xl border overflow-hidden"
        style={{
          width: 210,
          background: `rgba(167,139,250,0.07)`,
          borderColor: selected ? '#00d4ff' : `rgba(167,139,250,0.3)`,
          boxShadow: selected
            ? '0 0 0 2px #00d4ff, 0 16px 48px rgba(0,212,255,0.18)'
            : '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        {/* Top shimmer */}
        <div
          className="absolute top-0 inset-x-8 h-px"
          style={{ background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent)' }}
        />

        {/* Header */}
        <div className="flex items-center gap-2.5 px-3.5 pt-3 pb-2.5">
          <div
            className="flex items-center justify-center rounded-xl flex-shrink-0"
            style={{
              width: 38, height: 38,
              background: 'rgba(167,139,250,0.14)',
              boxShadow: '0 0 20px rgba(167,139,250,0.2)',
            }}
          >
            <NodeIcon name={iconName} size={18} color={color} strokeWidth={1.8} />
          </div>
          <div className="min-w-0">
            <p className="text-[8px] font-bold tracking-[0.14em] uppercase opacity-50" style={{ color }}>
              ORCHESTRATOR
            </p>
            <p className="text-[12px] font-bold leading-tight truncate" style={{ color: '#c4b5fd' }}>
              {label}
            </p>
            <p className="text-[9px] font-mono opacity-40 truncate">{subLabel}</p>
          </div>
        </div>

        {/* Footer */}
        <div
          className="flex items-center gap-1.5 px-3.5 py-2"
          style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
        >
          <div
            className="rounded-full flex-shrink-0"
            style={{
              width: 5, height: 5,
              background: statusColor,
              boxShadow: `0 0 6px ${statusColor}`,
            }}
          />
          <span className="text-[9px] font-semibold" style={{ color: statusColor }}>
            {status}
          </span>
          {durationLabel && (
            <span className="ml-auto text-[9px] font-mono opacity-35">{durationLabel}</span>
          )}
        </div>

        <Handle
          type="source"
          position={Position.Right}
          style={{ background: '#07070f', borderColor: 'rgba(167,139,250,0.5)', width: 10, height: 10 }}
        />
      </div>
    </motion.div>
  );
});
