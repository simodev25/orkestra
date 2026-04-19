// frontend/src/lib/test-lab/graph-layout.ts
import dagre from '@dagrejs/dagre';
import type { TestRunEvent, TestRunDiagnostic, TestRun } from './types';
import type { RunNode, RunEdge, PhaseKind, AgentNodeData } from './graph-types';

const NODE_W = 210;
const NODE_H = 108;

// ── Icon + colour registry ─────────────────────────────────────────────────
export const AGENT_ICONS: Record<string, { iconName: string; color: string }> = {
  identity_resolution_agent: { iconName: 'Fingerprint',   color: '#00d4ff' },
  chat_agent:                { iconName: 'MessageSquare',  color: '#a78bfa' },
  routing_agent:             { iconName: 'GitFork',        color: '#f59e0b' },
  classifier_agent:          { iconName: 'Tag',            color: '#10b981' },
  preparation_agent:         { iconName: 'ClipboardCheck', color: '#c4b5fd' },
  assertion_agent:           { iconName: 'ShieldCheck',    color: '#10b981' },
  diagnostic_agent:          { iconName: 'FileSearch2',    color: '#f59e0b' },
  verdict_agent:             { iconName: 'Award',          color: '#10b981' },
};

const PHASE_CFG: Record<
  PhaseKind,
  { iconName: string; color: string; label: string; nodeType: string }
> = {
  orchestrator: { iconName: 'Sun',           color: '#a78bfa', label: 'Orchestrator', nodeType: 'orchestratorNode' },
  preparation:  { iconName: 'ClipboardCheck', color: '#c4b5fd', label: 'Preparation',  nodeType: 'agentNode' },
  runtime:      { iconName: 'Bot',           color: '#00d4ff', label: 'Agent',         nodeType: 'agentNode' },
  assertions:   { iconName: 'ShieldCheck',   color: '#10b981', label: 'Assertions',    nodeType: 'agentNode' },
  diagnostics:  { iconName: 'FileSearch2',   color: '#f59e0b', label: 'Diagnostics',   nodeType: 'agentNode' },
  report:       { iconName: 'Award',         color: '#10b981', label: 'Verdict',       nodeType: 'agentNode' },
};

const EDGE_COLOURS: Record<PhaseKind, string> = {
  orchestrator: '#a78bfa',
  preparation:  '#c4b5fd',
  runtime:      '#00d4ff',
  assertions:   '#10b981',
  diagnostics:  '#f59e0b',
  report:       '#10b981',
};

// Map orchestrator tool names → target phase (fixed test-lab phases only)
export const TOOL_TO_PHASE: Record<string, PhaseKind> = {
  prepare_test_scenario:    'preparation',
  execute_target_agent:     'runtime',
  run_assertion_evaluation: 'assertions',
  run_diagnostic_analysis:  'diagnostics',
  compute_final_verdict:    'report',
};

/** pipeline_tool_call tool_name → phase key (e.g. "run_stay_discovery_agent" → "pipeline_stay_discovery_agent") */
function pipelineToolToPhase(toolName: string): string {
  // tool name is "run_{safe_id}", phase key is "pipeline_{safe_id}"
  return toolName.replace(/^run_/, 'pipeline_');
}

/** Config for dynamically created pipeline agent nodes */
function getPipelinePhaseCfg(phase: string): { iconName: string; color: string; label: string; nodeType: string } {
  // Derive a readable label from the phase key "pipeline_{agent_id}"
  const agentId = phase.replace(/^pipeline_/, '');
  const label = agentId
    .replace(/_agent$/, '')
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
  return { iconName: 'Bot', color: '#38bdf8', label, nodeType: 'agentNode' };
}

export type PlaybackStatus = 'pending' | 'running' | 'completed' | 'failed';

const PHASE_MAP_PB: Record<string, string> = {
  orchestrator: 'orchestrator',
  preparation:  'preparation',
  runtime:      'runtime',
  assertions:   'assertions',
  diagnostics:  'diagnostics',
  report:       'report',
  verdict:      'report',
};

const PHASE_START_EV = new Set([
  'phase_started', 'assertion_phase_started',
  'diagnostic_phase_started', 'report_phase_started',
]);

/**
 * Given a sorted event list and a playback cursor (ms from run start),
 * return the current status of each phase node and which edges are "active"
 * (tool call fired but target phase not started yet).
 */
export function computePlaybackState(
  events: TestRunEvent[],
  startTs: number,
  cutoffMs: number,
): {
  phaseStatuses: Record<string, PlaybackStatus>;
  activeEdgeTargets: Set<string>;
} {
  const cutoffTs = startTs + cutoffMs;

  const phaseStatuses: Record<string, PlaybackStatus> = {
    orchestrator: 'pending',
    preparation:  'pending',
    runtime:      'pending',
    assertions:   'pending',
    diagnostics:  'pending',
    report:       'pending',
  };

  const pipelineToolCallTimes: Record<string, number> = {};

  for (const ev of events) {
    const evTs = new Date(ev.timestamp).getTime();
    if (evTs > cutoffTs) continue;

    const rawPhase = ev.phase ?? '';
    const phase = PHASE_MAP_PB[rawPhase] ?? (rawPhase.startsWith('pipeline_') ? rawPhase : null);

    // Orchestrator lifecycle
    if (ev.event_type === 'run_created' || ev.event_type === 'orchestrator_started') {
      phaseStatuses['orchestrator'] = 'running';
    }
    if (ev.event_type === 'run_completed') {
      phaseStatuses['orchestrator'] = 'completed';
    }

    // Pipeline tool calls (create dynamic phase status entries)
    if (ev.event_type === 'pipeline_tool_call' && ev.details?.tool_name) {
      const toolName = ev.details.tool_name as string;
      pipelineToolCallTimes[toolName] = evTs;
      const pPhase = pipelineToolToPhase(toolName);
      if (!(pPhase in phaseStatuses)) {
        phaseStatuses[pPhase] = 'pending';
      }
    }

    // Phase lifecycle (fixed + dynamic pipeline phases)
    if (phase && phase !== 'orchestrator') {
      if (PHASE_START_EV.has(ev.event_type)) {
        phaseStatuses[phase] = 'running';
      }
      if (ev.event_type === 'phase_completed') {
        const msg = (ev.message ?? '').toLowerCase();
        phaseStatuses[phase] = (msg.includes('fail') || msg.includes('error'))
          ? 'failed' : 'completed';
      }
    }
  }

  // Active edges: pipeline tool call happened but target phase still pending
  const activeEdgeTargets = new Set<string>();
  for (const [toolName, _ts] of Object.entries(pipelineToolCallTimes)) {
    const target = pipelineToolToPhase(toolName);
    if (target && phaseStatuses[target] === 'pending') {
      activeEdgeTargets.add(target);
    }
  }

  return { phaseStatuses, activeEdgeTargets };
}

// ── Helpers ────────────────────────────────────────────────────────────────
function toTitle(agentId: string): string {
  return agentId
    .replace(/_agent$/, '')
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function detectStatus(evs: TestRunEvent[]): string {
  const done = evs.find((e) =>
    e.event_type === 'phase_completed' ||
    e.event_type === 'run_completed'
  );
  if (!done) return 'running';
  const msg = (done.message ?? '').toLowerCase();
  if (msg.includes('fail') || msg.includes('error')) return 'failed';
  if (msg.includes('warn')) return 'warning';
  return 'completed';
}

function detectDuration(evs: TestRunEvent[]): number | null {
  const start = evs.find((e) =>
    ['phase_started', 'assertion_phase_started', 'diagnostic_phase_started', 'report_phase_started'].includes(e.event_type)
  );
  const end = evs.find((e) => e.event_type === 'phase_completed');
  if (!start || !end) return null;
  return new Date(end.timestamp).getTime() - new Date(start.timestamp).getTime();
}

function parseOutput(raw: string | null): unknown {
  if (!raw) return null;
  // Try direct parse first
  try { return JSON.parse(raw); } catch { /* fall through */ }
  // Extract first JSON object from text (agent may wrap with prose)
  const match = raw.match(/\{[\s\S]*\}/);
  if (match) {
    try { return JSON.parse(match[0]); } catch { /* fall through */ }
  }
  // Return raw string so panel still shows something
  return raw.length > 0 ? raw : null;
}

// ── Main export ────────────────────────────────────────────────────────────
export function buildGraph(
  events: TestRunEvent[],
  run: TestRun,
  diagnostics: TestRunDiagnostic[]
): { nodes: RunNode[]; edges: RunEdge[] } {
  // 1. Group events by phase (preserve order of first appearance)
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

  function resolvePhase(rawPhase: string | null | undefined): string | null {
    if (!rawPhase) return null;
    if (PHASE_MAP[rawPhase]) return PHASE_MAP[rawPhase];
    if (rawPhase.startsWith('pipeline_')) return rawPhase; // dynamic pipeline phase
    return null;
  }

  const phaseOrder: string[] = [];
  const phaseEvs = new Map<string, TestRunEvent[]>();

  // Always include orchestrator first
  phaseOrder.push('orchestrator');
  phaseEvs.set('orchestrator', []);

  // Collect pipeline tool calls in order (for sequential edge building)
  const orderedPipelineCalls: Array<{ toolName: string; phase: string }> = [];

  for (const ev of events) {
    const phase = resolvePhase(ev.phase);
    if (!phase) continue;
    if (!phaseEvs.has(phase)) {
      phaseOrder.push(phase);
      phaseEvs.set(phase, []);
    }
    phaseEvs.get(phase)!.push(ev);

    // Track pipeline tool call order
    if (ev.event_type === 'pipeline_tool_call' && ev.details?.tool_name) {
      const toolName = ev.details.tool_name as string;
      const pPhase = pipelineToolToPhase(toolName);
      if (!orderedPipelineCalls.find((x) => x.phase === pPhase)) {
        orderedPipelineCalls.push({ toolName, phase: pPhase });
      }
    }
  }

  // Ensure orchestrator bucket gets events with no phase
  for (const ev of events) {
    if (!ev.phase || ev.phase === 'orchestrator' || ev.phase === 'orchestration') {
      phaseEvs.get('orchestrator')!.push(ev);
    }
  }

  // 2. Set up dagre graph
  const g = new dagre.graphlib.Graph();
  g.setDefaultEdgeLabel(() => ({}));
  g.setGraph({ rankdir: 'LR', ranksep: 130, nodesep: 70, marginx: 80, marginy: 80 });

  // 3. Build nodes
  const nodes: RunNode[] = [];

  phaseOrder.forEach((phase, index) => {
    const isPipeline = phase.startsWith('pipeline_');
    const cfg = isPipeline ? getPipelinePhaseCfg(phase) : PHASE_CFG[phase as PhaseKind];
    if (!cfg) return; // unknown fixed phase — skip
    const evList = phaseEvs.get(phase) ?? [];

    let iconName = cfg.iconName;
    let color = cfg.color;
    let label = cfg.label;
    let subLabel = isPipeline ? phase.replace(/^pipeline_/, '') : `${phase}_agent`;

    if (phase === 'runtime') {
      const agCfg = AGENT_ICONS[run.agent_id];
      if (agCfg) { iconName = agCfg.iconName; color = agCfg.color; }
      label = toTitle(run.agent_id);
      subLabel = run.agent_id;
    } else if (phase === 'orchestrator') {
      subLabel = 'master pipeline';
    }

    // For pipeline nodes: extract output from pipeline_agent_output event
    let pipelineOutput: unknown = null;
    if (isPipeline) {
      const outEv = evList.find((e) => e.event_type === 'pipeline_agent_output');
      if (outEv?.details?.output) {
        pipelineOutput = parseOutput(outEv.details.output as string);
      }
    }

    const data: AgentNodeData = {
      kind: phase,
      agentId: phase === 'runtime' ? run.agent_id : (isPipeline ? phase.replace(/^pipeline_/, '') : `${phase}_agent`),
      label,
      subLabel,
      iconName,
      color,
      status: detectStatus(evList),
      visible: phase === 'orchestrator',
      durationMs: phase === 'runtime' ? run.duration_ms ?? null : detectDuration(evList),
      events: evList,
      diagnostics: ['runtime', 'diagnostics'].includes(phase) ? diagnostics : [],
      output: phase === 'runtime' ? parseOutput(run.final_output) : pipelineOutput,
      index,
      verdict: phase === 'report' ? (run.verdict ?? null) : undefined,
      score:   phase === 'report' ? (run.score   ?? null) : undefined,
    };

    g.setNode(phase, { width: NODE_W, height: NODE_H });
    nodes.push({
      id: phase,
      type: cfg.nodeType,
      position: { x: 0, y: 0 }, // overwritten by dagre below
      data,
      width: NODE_W,
      height: NODE_H,
    });
  });

  // 4. Build edges
  const edges: RunEdge[] = [];
  const addedEdgeIds = new Set<string>();

  function addEdge(src: string, tgt: string, toolName: string | null, color: string) {
    const edgeId = `${src}->${tgt}`;
    if (addedEdgeIds.has(edgeId)) return;
    if (!phaseEvs.has(src) || !phaseEvs.has(tgt)) return;
    addedEdgeIds.add(edgeId);
    g.setEdge(src, tgt);
    edges.push({ id: edgeId, source: src, target: tgt, type: 'animatedEdge', data: { toolName, color } });
  }

  // 4a. Standard test-lab tool call edges (orchestrator → fixed phases)
  const toolCalls = events.filter(
    (e) => e.event_type === 'orchestrator_tool_call' && e.details?.tool_name
  );
  for (const tc of toolCalls) {
    const toolName = tc.details!.tool_name as string;
    const target = TOOL_TO_PHASE[toolName];
    if (!target || !phaseEvs.has(target)) continue;
    addEdge('orchestrator', target, toolName, EDGE_COLOURS['orchestrator']);
  }

  // 4b. Pipeline agent edges: runtime → pipeline_1 → pipeline_2 → … → last_pipeline
  if (orderedPipelineCalls.length > 0) {
    const PIPELINE_COLOUR = '#38bdf8';
    // runtime → first pipeline agent
    addEdge('runtime', orderedPipelineCalls[0].phase, orderedPipelineCalls[0].toolName, PIPELINE_COLOUR);
    // sequential pipeline → pipeline edges
    for (let i = 0; i < orderedPipelineCalls.length - 1; i++) {
      addEdge(orderedPipelineCalls[i].phase, orderedPipelineCalls[i + 1].phase, orderedPipelineCalls[i + 1].toolName, PIPELINE_COLOUR);
    }
    // last pipeline agent → assertions (if assertions node exists)
    const lastPhase = orderedPipelineCalls[orderedPipelineCalls.length - 1].phase;
    if (phaseEvs.has('assertions')) {
      addEdge(lastPhase, 'assertions', null, PIPELINE_COLOUR);
    }
  }

  // Fallback: connect adjacent phases in order if no edges were built at all
  if (edges.length === 0) {
    for (let i = 0; i < phaseOrder.length - 1; i++) {
      const src = phaseOrder[i];
      const tgt = phaseOrder[i + 1];
      const colour = EDGE_COLOURS[src as PhaseKind] ?? '#38bdf8';
      addEdge(src, tgt, null, colour);
    }
  }

  // 5. Apply dagre layout
  dagre.layout(g);

  // 6. Transfer positions
  for (const node of nodes) {
    const pos = g.node(node.id);
    if (pos) {
      node.position = { x: pos.x - NODE_W / 2, y: pos.y - NODE_H / 2 };
    }
  }

  return { nodes, edges };
}

/**
 * Calculate a viewport that fits all nodes in a given viewport size.
 * Used as the defaultViewport for ReactFlow so the fit is immediate.
 */
export function calcInitialViewport(
  nodes: RunNode[],
  viewW: number,
  viewH: number,
  padding = 0.18,
): { x: number; y: number; zoom: number } {
  if (nodes.length === 0) return { x: 0, y: 0, zoom: 1 };

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const n of nodes) {
    const nx = n.position.x;
    const ny = n.position.y;
    const nw = n.width ?? NODE_W;
    const nh = n.height ?? NODE_H;
    minX = Math.min(minX, nx);
    minY = Math.min(minY, ny);
    maxX = Math.max(maxX, nx + nw);
    maxY = Math.max(maxY, ny + nh);
  }

  const graphW = maxX - minX;
  const graphH = maxY - minY;

  const zoom = Math.min(
    (viewW * (1 - padding)) / graphW,
    (viewH * (1 - padding)) / graphH,
    1.5, // don't zoom in too much
  );

  const x = (viewW - graphW * zoom) / 2 - minX * zoom;
  const y = (viewH - graphH * zoom) / 2 - minY * zoom;

  return { x, y, zoom };
}
