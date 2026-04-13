"use client";

import { useCallback, useMemo, useState, useEffect, useRef } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type NodeMouseHandler,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { buildGraph } from '@/lib/test-lab/graph-layout';
import type { TestRun, TestRunEvent, TestRunDiagnostic } from '@/lib/test-lab/types';
import type { AgentNodeData, RunNode, RunEdge } from '@/lib/test-lab/graph-types';

import { OrchestratorNode } from './nodes/OrchestratorNode';
import { AgentNode } from './nodes/AgentNode';
import { AnimatedEdge } from './edges/AnimatedEdge';
import { DetailPanel } from './DetailPanel';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const NODE_TYPES: any = {
  orchestratorNode: OrchestratorNode,
  agentNode: AgentNode,
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const EDGE_TYPES: any = {
  animatedEdge: AnimatedEdge,
};

interface RunGraphProps {
  run: TestRun;
  events: TestRunEvent[];
  diagnostics: TestRunDiagnostic[];
}

/** Total animation duration to replay the full run (ms) */
const ANIM_DURATION_MS = 5000;

/** Events that signal a phase node has started */
const PHASE_START_EVENTS = new Set([
  'subagent_start',   // preparation agent starting
  'phase_start',      // runtime phase starting
  'phase_started',    // generic fallback
  'assertion_phase_started',
  'diagnostic_phase_started',
  'report_phase_started',
]);

/** Events that signal a phase node has completed */
const PHASE_DONE_EVENTS = new Set([
  'subagent_done',    // preparation agent done
  'agent_done',       // runtime agent done
  'phase_completed',  // generic fallback
]);

/** Normalize event phase strings to node IDs */
const PHASE_MAP: Record<string, string> = {
  orchestration: 'orchestrator',
  orchestrator:  'orchestrator',
  preparation:   'preparation',
  runtime:       'runtime',
  assertions:    'assertions',
  diagnostics:   'diagnostics',
  report:        'report',
  verdict:       'report',
};

/** How long the edge pulses before the node pops in (ms, in animation time) */
const EDGE_LEAD_MS = 400;

export function RunGraph({ run, events, diagnostics }: RunGraphProps) {
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildGraph(events, run, diagnostics),
    [events, run, diagnostics]
  );

  const [nodes, , onNodesChange] = useNodesState<RunNode>(initNodes);
  const [edges, , onEdgesChange] = useEdgesState<RunEdge>(initEdges);
  const [selectedNodeData, setSelectedNodeData] = useState<AgentNodeData | null>(null);

  // ── Progressive reveal state ───────────────────────────────────────────────
  const [visiblePhases, setVisiblePhases]       = useState<Set<string>>(new Set(['orchestrator']));
  const [activeEdgeTargets, setActiveEdgeTargets] = useState<Set<string>>(new Set());
  const [phaseStatuses, setPhaseStatuses]       = useState<Record<string, string>>({ orchestrator: 'running' });

  const timeoutsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Schedule progressive reveal driven by event timestamps
  useEffect(() => {
    // Clear any running animation
    timeoutsRef.current.forEach(t => clearTimeout(t));
    timeoutsRef.current = [];

    if (!events.length) {
      // No events → show everything at final status immediately
      setVisiblePhases(new Set(initNodes.map(n => n.id)));
      const statuses: Record<string, string> = {};
      for (const n of initNodes) statuses[n.id] = n.data.status;
      setPhaseStatuses(statuses);
      return;
    }

    const timestamps = events.map(e => new Date(e.timestamp).getTime());
    const startTs    = Math.min(...timestamps);
    const totalMs    = Math.max(...timestamps) - startTs || 1;
    const scale      = ANIM_DURATION_MS / totalMs;

    const schedule = (delayMs: number, fn: () => void) => {
      const t = setTimeout(fn, Math.max(0, delayMs));
      timeoutsRef.current.push(t);
    };

    for (const ev of events) {
      const delay = (new Date(ev.timestamp).getTime() - startTs) * scale;

      // Orchestrator starts
      if (ev.event_type === 'run_started') {
        schedule(delay, () => {
          setVisiblePhases(prev => new Set([...prev, 'orchestrator']));
          setPhaseStatuses(prev => ({ ...prev, orchestrator: 'running' }));
        });
      }

      // Phase/subagent starts → activate edge immediately, reveal node after a short lead
      if (PHASE_START_EVENTS.has(ev.event_type) && ev.phase) {
        const nodeId = PHASE_MAP[ev.phase];
        if (nodeId && nodeId !== 'orchestrator') {
          // Edge pulses first
          schedule(delay, () =>
            setActiveEdgeTargets(prev => new Set([...prev, nodeId]))
          );
          // Node springs in after lead time
          schedule(delay + EDGE_LEAD_MS, () => {
            setVisiblePhases(prev => new Set([...prev, nodeId]));
            setActiveEdgeTargets(prev => {
              const next = new Set(prev);
              next.delete(nodeId);
              return next;
            });
            setPhaseStatuses(prev => ({ ...prev, [nodeId]: 'running' }));
          });
        }
      }

      // Phase/subagent done → mark final status
      if (PHASE_DONE_EVENTS.has(ev.event_type) && ev.phase) {
        const nodeId = PHASE_MAP[ev.phase];
        if (nodeId) {
          schedule(delay, () => {
            const msg = (ev.message ?? '').toLowerCase();
            const s = msg.includes('fail') || msg.includes('error') ? 'failed'
              : msg.includes('warn') ? 'warning' : 'completed';
            setPhaseStatuses(prev => ({ ...prev, [nodeId]: s }));
          });
        }
      }

      // Run completed → reveal verdict/report node, then mark orchestrator done
      if (ev.event_type === 'run_completed') {
        // Activate edge to report node
        schedule(delay, () =>
          setActiveEdgeTargets(prev => new Set([...prev, 'report']))
        );
        // Reveal report node after edge lead
        schedule(delay + EDGE_LEAD_MS, () => {
          setVisiblePhases(prev => new Set([...prev, 'report']));
          setActiveEdgeTargets(prev => {
            const next = new Set(prev);
            next.delete('report');
            return next;
          });
          const msg = (ev.message ?? '').toLowerCase();
          const reportStatus = msg.includes('fail') || msg.includes('error') ? 'failed'
            : msg.includes('warn') ? 'warning' : 'completed';
          setPhaseStatuses(prev => ({
            ...prev,
            orchestrator: 'completed',
            report: reportStatus,
          }));
        });
      }
    }

    return () => {
      timeoutsRef.current.forEach(t => clearTimeout(t));
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events]);

  // ── Derive display state ───────────────────────────────────────────────────
  const displayNodes = useMemo(
    () => nodes.map(node => ({
      ...node,
      data: {
        ...node.data,
        visible: visiblePhases.has(node.id),
        status:  phaseStatuses[node.id] ?? node.data.status,
      },
    })),
    [nodes, visiblePhases, phaseStatuses]
  );

  const displayEdges = useMemo(
    () => edges.map(edge => ({
      ...edge,
      data: {
        ...edge.data,
        visible: visiblePhases.has(edge.target),
        active:  activeEdgeTargets.has(edge.target),
      },
    })),
    [edges, visiblePhases, activeEdgeTargets]
  );

  // ── Interaction ────────────────────────────────────────────────────────────
  const onNodeClick: NodeMouseHandler = useCallback((_evt, node) => {
    setSelectedNodeData(node.data as AgentNodeData);
  }, []);

  const onPaneClick = useCallback(() => setSelectedNodeData(null), []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onInit = useCallback((instance: any) => {
    window.requestAnimationFrame(() => {
      instance.fitView({ padding: 0.18, maxZoom: 1.4, duration: 0 });
    });
  }, []);

  return (
    <div className="flex flex-col" style={{ height: '100%' }}>
      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1" style={{ background: '#07070f' }}>
          <ReactFlow
            nodes={displayNodes}
            edges={displayEdges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={NODE_TYPES}
            edgeTypes={EDGE_TYPES}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            onInit={onInit}
            minZoom={0.3}
            maxZoom={2.0}
            proOptions={{ hideAttribution: true }}
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={32}
              size={1}
              color="rgba(255,255,255,0.04)"
            />
            <Controls
              position="bottom-right"
              style={{
                background: 'rgba(9,9,18,0.9)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 10,
              }}
            />
            <MiniMap
              position="bottom-left"
              nodeColor={(node) => {
                const d = node.data as AgentNodeData;
                if (!d?.visible)              return 'transparent';
                if (d?.status === 'running')  return d?.color ?? '#a78bfa';
                return d?.color ?? '#52525b';
              }}
              style={{
                background: 'rgba(9,9,18,0.85)',
                border: '1px solid rgba(255,255,255,0.08)',
                borderRadius: 10,
              }}
              maskColor="rgba(7,7,15,0.7)"
            />
          </ReactFlow>
        </div>

        <DetailPanel node={selectedNodeData} onClose={onPaneClick} />
      </div>
    </div>
  );
}
