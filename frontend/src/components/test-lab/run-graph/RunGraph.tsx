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
  effectDenials?: Array<{ id: string; mcp_id: string; calling_agent_id: string | null; effects: string[]; blocked_at: string | null }>;
}

/** Replay duration for completed runs */
const ANIM_DURATION_MS = 5000;

/** Events that mean a phase just started */
const PHASE_START_EVENTS = new Set([
  'phase_start', 'phase_started',
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
  judgment:      'report',
  assertions:    'assertions',
  diagnostics:   'diagnostics',
  report:        'report',
  verdict:       'report',
};

/** Resolve a raw event phase to a ReactFlow node ID (handles dynamic pipeline_* phases). */
function resolveNodeId(rawPhase: string | null | undefined): string | null {
  if (!rawPhase) return null;
  if (PHASE_MAP[rawPhase]) return PHASE_MAP[rawPhase];
  if (rawPhase.startsWith('pipeline_')) return rawPhase; // dynamic pipeline node IDs
  return null;
}

/** Edge pulses this long before the target node springs in */
const EDGE_LEAD_MS = 400;

function statusFromEvent(ev: TestRunEvent): string {
  const msg = (ev.message ?? '').toLowerCase();
  if (msg.includes('fail') || msg.includes('error')) return 'failed';
  if (msg.includes('warn')) return 'warning';
  return 'completed';
}

export function RunGraph({ run, events, diagnostics, effectDenials = [] }: RunGraphProps) {
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
  /** ReactFlow instance — captured in onInit */
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rfInstanceRef    = useRef<any>(null);
  /** Debounce timer for fitView to avoid layout thrash */
  const fitViewTimerRef  = useRef<ReturnType<typeof setTimeout> | null>(null);

  const isLive = run.status === 'running' || run.status === 'queued';

  // ── Sync ReactFlow nodes/edges when graph structure grows (live mode) ───────
  useEffect(() => { setNodes(initNodes); }, [initNodes, setNodes]);
  useEffect(() => { setEdges(initEdges); }, [initEdges, setEdges]);

  // ── Safety net: for completed runs ensure every node is eventually visible ──
  // If new nodes appear in initNodes (e.g. pipeline agents) after the replay
  // locked (replayDoneRef = true), this hook reveals them immediately.
  useEffect(() => {
    if (isLive) return; // live mode handles visibility via event stream
    const allIds = new Set(initNodes.map((n) => n.id));
    setVisiblePhases((prev) => {
      const missing = [...allIds].filter((id) => !prev.has(id));
      if (missing.length === 0) return prev;
      return new Set([...prev, ...missing]);
    });
    setPhaseStatuses((prev) => {
      const updated = { ...prev };
      let changed = false;
      for (const id of allIds) {
        if (!(id in updated)) { updated[id] = 'completed'; changed = true; }
      }
      return changed ? updated : prev;
    });
  }, [initNodes, isLive]);

  // ── Core animation logic ────────────────────────────────────────────────────
  useEffect(() => {
    if (!isLive) {
      // ── LIVE → COMPLETED TRANSITION ────────────────────────────────────────
      // Live mode already applied most state. Keep flushing any events that
      // arrive AFTER isLive switches (e.g. run_completed from fetchData()).
      // Do NOT gate this path with replayDoneRef — new events must always land.
      if (processedIdsRef.current.size > 0) {
        replayDoneRef.current = true; // block replay mode
        const remaining = events.filter(ev => !processedIdsRef.current.has(ev.id));
        if (remaining.length === 0) return;
        remaining.forEach(ev => processedIdsRef.current.add(ev.id));
        for (const ev of remaining) {
          if (ev.event_type === 'run_started') {
            setVisiblePhases(prev => new Set([...prev, 'orchestrator']));
            setPhaseStatuses(prev => ({ ...prev, orchestrator: 'running' }));
          }
          if (PHASE_START_EVENTS.has(ev.event_type) && ev.phase) {
            const nodeId = resolveNodeId(ev.phase);
            if (nodeId && nodeId !== 'orchestrator') {
              setVisiblePhases(prev => new Set([...prev, nodeId]));
              setPhaseStatuses(prev => ({ ...prev, [nodeId]: 'running' }));
            }
          }
          if (PHASE_DONE_EVENTS.has(ev.event_type) && ev.phase) {
            const nodeId = resolveNodeId(ev.phase);
            if (nodeId) {
              setVisiblePhases(prev => prev.has(nodeId) ? prev : new Set([...prev, nodeId]));
              setPhaseStatuses(prev => ({ ...prev, [nodeId]: statusFromEvent(ev) }));
            }
          }
          if (ev.event_type === 'run_completed') {
            setVisiblePhases(prev => new Set([...prev, 'report']));
            setPhaseStatuses(prev => ({
              ...prev,
              orchestrator: 'completed',
              report: statusFromEvent(ev),
            }));
          }
        }
        return;
      }

      // ── REPLAY MODE (fresh page load for a completed run) ─────────────────
      if (replayDoneRef.current) return;
      // Wait for events to load before locking replay — otherwise we'd lock
      // with an empty initNodes list and block the real replay forever.
      if (!events.length) return;

      replayDoneRef.current = true;
      timeoutsRef.current.forEach(t => clearTimeout(t));
      timeoutsRef.current = [];

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
          const nodeId = resolveNodeId(ev.phase);
          if (nodeId && nodeId !== 'orchestrator') {
            schedule(delay, () =>
              setActiveEdgeTargets(prev => new Set([...prev, nodeId]))
            );
            schedule(delay + EDGE_LEAD_MS, () => {
              setVisiblePhases(prev => new Set([...prev, nodeId]));
              setActiveEdgeTargets(prev => { const n = new Set(prev); n.delete(nodeId); return n; });
              setPhaseStatuses(prev => ({
                ...prev,
                [nodeId]: ['completed', 'failed', 'warning'].includes(prev[nodeId]) ? prev[nodeId] : 'running',
              }));
            });
          }
        }

        if (PHASE_DONE_EVENTS.has(ev.event_type) && ev.phase) {
          const nodeId = resolveNodeId(ev.phase);
          if (nodeId) {
            schedule(delay, () => {
              setVisiblePhases(prev => prev.has(nodeId) ? prev : new Set([...prev, nodeId]));
              setPhaseStatuses(prev => ({ ...prev, [nodeId]: statusFromEvent(ev) }));
            });
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

      // On cleanup (unmount or StrictMode remount): cancel timeouts and reset the
      // replay lock so a remount can re-schedule from scratch.
      return () => {
        replayDoneRef.current = false;
        timeoutsRef.current.forEach(t => clearTimeout(t));
        timeoutsRef.current = [];
      };
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
            setPhaseStatuses(prev => ({
              ...prev,
              [nodeId]: ['completed', 'failed', 'warning'].includes(prev[nodeId]) ? prev[nodeId] : 'running',
            }));
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
        const nodeId = resolveNodeId(ev.phase);
        if (nodeId && nodeId !== 'orchestrator') revealNode(nodeId, EDGE_LEAD_MS);
      }

      if (PHASE_DONE_EVENTS.has(ev.event_type) && ev.phase) {
        const nodeId = resolveNodeId(ev.phase);
        if (nodeId) {
          setVisiblePhases(prev => prev.has(nodeId) ? prev : new Set([...prev, nodeId]));
          setPhaseStatuses(prev => ({ ...prev, [nodeId]: statusFromEvent(ev) }));
        }
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
        toolName: edge.data?.toolName ?? null,
        color:    edge.data?.color ?? '#52525b',
        visible:  visiblePhases.has(edge.target),
        active:   activeEdgeTargets.has(edge.target),
      },
    })),
    [edges, visiblePhases, activeEdgeTargets]
  );

  // ── Auto-fitView whenever new nodes become visible ─────────────────────────
  useEffect(() => {
    if (!rfInstanceRef.current) return;
    // Cancel previous timer if visiblePhases changes rapidly (e.g. during replay)
    if (fitViewTimerRef.current) {
      clearTimeout(fitViewTimerRef.current);
    }
    fitViewTimerRef.current = setTimeout(() => {
      window.requestAnimationFrame(() => {
        rfInstanceRef.current?.fitView({ padding: 0.18, maxZoom: 1.4, duration: 400 });
      });
      fitViewTimerRef.current = null;
    }, 200);
  }, [visiblePhases]);

  // ── Interaction ────────────────────────────────────────────────────────────
  const onNodeClick: NodeMouseHandler = useCallback((_evt, node) => {
    setSelectedNodeData(node.data as AgentNodeData);
  }, []);

  const onPaneClick = useCallback(() => setSelectedNodeData(null), []);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onInit = useCallback((instance: any) => {
    rfInstanceRef.current = instance;
    window.requestAnimationFrame(() => {
      instance.fitView({ padding: 0.18, maxZoom: 1.4, duration: 0 });
    });
  }, []);

  return (
    <div className="flex flex-col" style={{ height: '100%' }}>
      {/* Effect denial banner */}
      {effectDenials.length > 0 && (
        <div
          className="flex items-center gap-2 px-3 py-1.5 flex-wrap"
          style={{
            background: 'color-mix(in oklch, var(--ork-red) 8%, transparent)',
            borderBottom: '1px solid color-mix(in oklch, var(--ork-red) 25%, transparent)',
            flexShrink: 0,
          }}
        >
          <span style={{ color: 'var(--ork-red)', fontSize: 11, fontWeight: 700 }}>⛔ BLOCKED EFFECTS</span>
          {effectDenials.map((d) => (
            <span
              key={d.id}
              title={`effects [${d.effects.join(', ')}] are forbidden for this agent`}
              style={{
                fontSize: 10,
                fontFamily: 'var(--font-mono)',
                color: 'var(--ork-red)',
                background: 'color-mix(in oklch, var(--ork-red) 12%, transparent)',
                border: '1px solid color-mix(in oklch, var(--ork-red) 30%, transparent)',
                borderRadius: 4,
                padding: '1px 6px',
              }}
            >
              {d.mcp_id}: {d.effects.join(', ')}
            </span>
          ))}
        </div>
      )}
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
