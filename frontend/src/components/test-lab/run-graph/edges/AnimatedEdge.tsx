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

  const color    = data?.color ?? '#52525b';
  const toolName = data?.toolName ?? null;
  const active   = data?.active  ?? false;
  const visible  = data?.visible ?? false;

  // Edge is shown when active (tool call fired) OR when the target node is revealed
  const show = active || visible;

  const glowOpacity  = active ? 0.5  : 0.2;
  const lineOpacity  = active ? 1.0  : 0.6;
  const animDuration = active ? '0.6s' : '2s';
  const strokeW      = active ? 6 : 4;

  return (
    <>
      {/* Glow layer */}
      <BaseEdge
        path={edgePath}
        interactionWidth={0}
        style={{
          stroke: color,
          strokeWidth: strokeW,
          strokeOpacity: show ? glowOpacity : 0,
          filter: `blur(${active ? 4 : 3}px)`,
          strokeDasharray: '8 5',
          animation: show ? `edgeDash ${animDuration} linear infinite` : 'none',
          transition: 'stroke-opacity 0.4s',
        }}
      />
      {/* Main edge */}
      <BaseEdge
        id={id}
        path={edgePath}
        style={{
          stroke: color,
          strokeWidth: active ? 2 : 1.5,
          strokeOpacity: show ? lineOpacity : 0,
          strokeDasharray: '8 5',
          animation: show ? `edgeDash ${animDuration} linear infinite` : 'none',
          transition: 'stroke-opacity 0.4s',
        }}
      />
      {/* Active pulse dot traveling along edge */}
      {active && (
        <circle r="4" fill={color} style={{ filter: `drop-shadow(0 0 6px ${color})` }}>
          <animateMotion
            dur="0.8s"
            repeatCount="indefinite"
            path={edgePath}
          />
        </circle>
      )}
      {/* Tool chip label */}
      {toolName && show && (
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
                background: active ? 'rgba(7,7,15,0.98)' : 'rgba(7,7,15,0.92)',
                borderColor: active ? `${color}66` : 'rgba(255,255,255,0.1)',
                color: active ? color : '#52525b',
                backdropFilter: 'blur(8px)',
                whiteSpace: 'nowrap',
                transition: 'color 0.3s, border-color 0.3s',
              }}
            >
              <span
                style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: color,
                  flexShrink: 0,
                  boxShadow: active ? `0 0 8px ${color}` : `0 0 4px ${color}66`,
                  animation: active ? 'dotBlink 0.6s ease-in-out infinite' : 'none',
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
