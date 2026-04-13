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
const NODE_TYPES: any = { orchestratorNode: OrchestratorNode, agentNode: AgentNode };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const EDGE_TYPES: any = { animatedEdge: AnimatedEdge };

interface RunGraphProps {
  run: TestRun;
  events: TestRunEvent[];
  diagnostics: TestRunDiagnostic[];
}

/** Replay duration for completed runs */
const ANIM_DURATION_MS = 5000;

/** Events that mean a phase just started */
const PHASE_START_EVENTS = new Set([
  'subagent_start', 'phase_start', 'phase_started',
  'assertion_phase_started', 'diagnostic_phase_started', 'report_phase_started',
]);

/** Events that mean a phase just finished */
const PHASE_DONE_EVENTS = new Set([
  'subagent_done', 'agent_done', 'phase_completed',
]);

/** Normalize API phase strings to ReactFlow node IDs */
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

/** Edge pulses this long before the target node springs in */
const EDGE_LEAD_MS = 400;

function statusFromEvent(ev: TestRunEvent): string {
  const msg = (ev.message ?? '').toLowerCase();
  if (msg.includes('fail') || msg.includes('error')) return 'failed';
  if (msg.includes('warn')) return 'warning';
  return 'completed';
}

export function RunGraph({ run, events, diagnostics }: RunGraphProps) {
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildGraph(events, run, diagnostics),
    [events, run, diagnostics]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<RunNode>(initNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<RunEdge>(initEdges);
  const [selectedNodeData, setSelectedNodeData] = useState<AgentNodeData | null>(null);

  // ── Animation state ────────────────────────────────────────────────────────
  const [visiblePhases, setVisiblePhases]         = useState<Set<string>>(new Set(['orchestrator']));
  const [activeEdgeTargets, setActiveEdgeTargets] = useState<Set<string>>(new Set());
  const [phaseStatuses, setPhaseStatuses]         = useState<Record<string, string>>({ orchestrator: 'running' });

  const timeoutsRef      = useRef<ReturnType<typeof setTimeout>[]>([]);
  /** IDs of events already processed (live mode) */
  const processedIdsRef  = useRef<Set<string>>(new Set());
  /** True once the completed-run replay has been scheduled */
  const replayDoneRef    = useRef(false);

  const isLive = run.status === 'running' || run.status === 'queued';

  // ── Sync ReactFlow nodes/edges when graph structure grows (live mode) ───────
  useEffect(() => { setNodes(initNodes); }, [initNodes, setNodes]);
  useEffect(() => { setEdges(initEdges); }, [initEdges, setEdges]);

  // ── Core animation logic ────────────────────────────────────────────────────
  useEffect(() => {
    if (!isLive) {
      // ── REPLAY MODE (completed / failed run) ──────────────────────────────
      // Only schedule once — don't restart when parent re-renders
      if (replayDoneRef.current) return;
      replayDoneRef.current = true;

      timeoutsRef.current.forEach(t => clearTimeout(t));
      timeoutsRef.current = [];

      if (!events.length) {
        setVisiblePhases(new Set(initNodes.map(n => n.id)));
        const s: Record<string, string> = {};
        initNodes.forEach(n => { s[n.id] = n.data.status; });
        setPhaseStatuses(s);
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

        if (ev.event_type === 'run_started') {
          schedule(delay, () => {
            setVisiblePhases(prev => new Set([...prev, 'orchestrator']));
            setPhaseStatuses(prev => ({ ...prev, orchestrator: 'running' }));
          });
        }

        if (PHASE_START_EVENTS.has(ev.event_type) && ev.phase) {
          const nodeId = PHASE_MAP[ev.phase];
          if (nodeId && nodeId !== 'orchestrator') {
            schedule(delay, () =>
              setActiveEdgeTargets(prev => new Set([...prev, nodeId]))
            );
            schedule(delay + EDGE_LEAD_MS, () => {
              setVisiblePhases(prev => new Set([...prev, nodeId]));
              setActiveEdgeTargets(prev => { const n = new Set(prev); n.delete(nodeId); return n; });
              setPhaseStatuses(prev => ({ ...prev, [nodeId]: 'running' }));
            });
          }
        }

        if (PHASE_DONE_EVENTS.has(ev.event_type) && ev.phase) {
          const nodeId = PHASE_MAP[ev.phase];
          if (nodeId) {
            schedule(delay, () =>
              setPhaseStatuses(prev => ({ ...prev, [nodeId]: statusFromEvent(ev) }))
            );
          }
        }

        if (ev.event_type === 'run_completed') {
          schedule(delay, () =>
            setActiveEdgeTargets(prev => new Set([...prev, 'report']))
          );
          schedule(delay + EDGE_LEAD_MS, () => {
            setVisiblePhases(prev => new Set([...prev, 'report']));
            setActiveEdgeTargets(prev => { const n = new Set(prev); n.delete('report'); return n; });
            setPhaseStatuses(prev => ({
              ...prev,
              orchestrator: 'completed',
              report: statusFromEvent(ev),
            }));
          });
        }
      }

      return () => timeoutsRef.current.forEach(t => clearTimeout(t));
    }

    // ── LIVE MODE (run still in progress) ────────────────────────────────────
    // First time: wasEmpty = true → apply current events immediately (no anim)
    // Subsequent calls: only new events, with edge-lead animation
    const wasFirstBatch = processedIdsRef.current.size === 0;
    const newEvents = events.filter(ev => !processedIdsRef.current.has(ev.id));
    if (newEvents.length === 0) return;

    newEvents.forEach(ev => processedIdsRef.current.add(ev.id));

    for (const ev of newEvents) {
      const animated = !wasFirstBatch; // historical → instant; new → animate

      const revealNode = (nodeId: string, leadMs: number) => {
        if (animated) {
          setActiveEdgeTargets(prev => new Set([...prev, nodeId]));
          const t = setTimeout(() => {
            setVisiblePhases(prev => new Set([...prev, nodeId]));
            setActiveEdgeTargets(prev => { const n = new Set(prev); n.delete(nodeId); return n; });
            setPhaseStatuses(prev => ({ ...prev, [nodeId]: 'running' }));
          }, leadMs);
          timeoutsRef.current.push(t);
        } else {
          setVisiblePhases(prev => new Set([...prev, nodeId]));
          setPhaseStatuses(prev => ({ ...prev, [nodeId]: 'running' }));
        }
      };

      if (ev.event_type === 'run_started') {
        setVisiblePhases(prev => new Set([...prev, 'orchestrator']));
        setPhaseStatuses(prev => ({ ...prev, orchestrator: 'running' }));
      }

      if (PHASE_START_EVENTS.has(ev.event_type) && ev.phase) {
        const nodeId = PHASE_MAP[ev.phase];
        if (nodeId && nodeId !== 'orchestrator') revealNode(nodeId, EDGE_LEAD_MS);
      }

      if (PHASE_DONE_EVENTS.has(ev.event_type) && ev.phase) {
        const nodeId = PHASE_MAP[ev.phase];
        if (nodeId) setPhaseStatuses(prev => ({ ...prev, [nodeId]: statusFromEvent(ev) }));
      }

      if (ev.event_type === 'run_completed') {
        if (animated) {
          setActiveEdgeTargets(prev => new Set([...prev, 'report']));
          const t = setTimeout(() => {
            setVisiblePhases(prev => new Set([...prev, 'report']));
            setActiveEdgeTargets(prev => { const n = new Set(prev); n.delete('report'); return n; });
            setPhaseStatuses(prev => ({
              ...prev,
              orchestrator: 'completed',
              report: statusFromEvent(ev),
            }));
          }, EDGE_LEAD_MS);
          timeoutsRef.current.push(t);
        } else {
          setVisiblePhases(prev => new Set([...prev, 'report']));
          setPhaseStatuses(prev => ({
            ...prev,
            orchestrator: 'completed',
            report: statusFromEvent(ev),
          }));
        }
      }
    }

    return () => timeoutsRef.current.forEach(t => clearTimeout(t));

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events, isLive]);

  // ── Display nodes / edges with animation overlay ───────────────────────────
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
            <Background variant={BackgroundVariant.Dots} gap={32} size={1} color="rgba(255,255,255,0.04)" />
            <Controls
              position="bottom-right"
              style={{ background: 'rgba(9,9,18,0.9)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}
            />
            <MiniMap
              position="bottom-left"
              nodeColor={(node) => {
                const d = node.data as AgentNodeData;
                if (!d?.visible)             return 'transparent';
                if (d?.status === 'running') return d?.color ?? '#a78bfa';
                return d?.color ?? '#52525b';
              }}
              style={{ background: 'rgba(9,9,18,0.85)', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 10 }}
              maskColor="rgba(7,7,15,0.7)"
            />
          </ReactFlow>
        </div>
        <DetailPanel node={selectedNodeData} onClose={onPaneClick} />
      </div>
    </div>
  );
}
