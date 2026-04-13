"use client";

import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
  type Edge,
} from '@xyflow/react';
import type { EdgeData } from '@/lib/test-lab/graph-types';

type AnimatedEdgeType = Edge<EdgeData, 'animatedEdge'>;

export function AnimatedEdge({
  id,
  sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition,
  data,
}: EdgeProps<AnimatedEdgeType>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY, sourcePosition,
    targetX, targetY, targetPosition,
  });

  const color = data?.color ?? '#52525b';
  const toolName = data?.toolName ?? null;

  return (
    <>
      {/* Glow layer */}
      <BaseEdge
        path={edgePath}
        interactionWidth={0}
        style={{
          stroke: color,
          strokeWidth: 4,
          strokeOpacity: 0.2,
          filter: 'blur(3px)',
          strokeDasharray: '8 5',
          animation: 'edgeDash 2s linear infinite',
        }}
      />
      {/* Main edge */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: color,
          strokeWidth: 1.5,
          strokeOpacity: 0.6,
          strokeDasharray: '8 5',
          animation: 'edgeDash 2s linear infinite',
        }}
      />
      {/* Tool chip label */}
      {toolName && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: 'absolute',
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: 'all',
            }}
            className="nodrag nopan"
          >
            <span
              className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[9px] font-mono font-semibold"
              style={{
                background: 'rgba(7,7,15,0.92)',
                borderColor: 'rgba(255,255,255,0.1)',
                color: '#52525b',
                backdropFilter: 'blur(8px)',
                whiteSpace: 'nowrap',
              }}
            >
              <span
                style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: color, flexShrink: 0,
                  boxShadow: `0 0 6px ${color}`,
                }}
              />
              {toolName}
            </span>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
