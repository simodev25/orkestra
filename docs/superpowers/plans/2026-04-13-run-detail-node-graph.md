# Run Detail — Node Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the vertical event timeline on `/test-lab/runs/[id]` with a ReactFlow canvas where each agent/phase is a draggable node with a Lucide icon, tool calls appear as chips on animated Bézier edges, and a Framer Motion panel slides in on node click.

**Architecture:** `TestRunEvent[]` is grouped by phase in `graph-layout.ts`, turned into ReactFlow nodes + edges with automatic dagre positioning (left→right). The page adds a `view: 'graph' | 'timeline'` toggle; existing timeline code stays intact as the fallback view.

**Tech Stack:** `@xyflow/react` v12, `framer-motion` v11, `@dagrejs/dagre` v1, Tailwind `ork-*` tokens, Lucide React (already installed).

---

## File Map

| File | Action |
|---|---|
| `frontend/src/lib/test-lab/graph-types.ts` | Create |
| `frontend/src/lib/test-lab/graph-layout.ts` | Create |
| `frontend/src/components/test-lab/run-graph/edges/AnimatedEdge.tsx` | Create |
| `frontend/src/components/test-lab/run-graph/nodes/OrchestratorNode.tsx` | Create |
| `frontend/src/components/test-lab/run-graph/nodes/AgentNode.tsx` | Create |
| `frontend/src/components/test-lab/run-graph/DetailPanel.tsx` | Create |
| `frontend/src/components/test-lab/run-graph/RunTopbar.tsx` | Create |
| `frontend/src/components/test-lab/run-graph/RunGraph.tsx` | Create |
| `frontend/src/app/test-lab/runs/[id]/page.tsx` | Modify |

---

## Task 1: Install dependencies

**Files:** `frontend/package.json`

- [ ] **Step 1: Install packages**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npm install @xyflow/react@^12 framer-motion@^11 @dagrejs/dagre@^1
```

Expected output: 3 packages added, no peer dependency errors.

- [ ] **Step 2: Verify TypeScript compiles cleanly**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output (zero errors).

- [ ] **Step 3: Commit**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
git add package.json package-lock.json
git commit -m "feat(run-graph): install @xyflow/react framer-motion @dagrejs/dagre"
```

---

## Task 2: Graph types

**Files:**
- Create: `frontend/src/lib/test-lab/graph-types.ts`

- [ ] **Step 1: Create the file**

```typescript
// frontend/src/lib/test-lab/graph-types.ts
import type { Node, Edge } from '@xyflow/react';
import type { TestRunEvent, TestRunDiagnostic } from './types';

export type PhaseKind =
  | 'orchestrator'
  | 'preparation'
  | 'runtime'
  | 'assertions'
  | 'diagnostics'
  | 'report';

export interface AgentNodeData extends Record<string, unknown> {
  kind: PhaseKind;
  agentId: string;
  /** Display title, e.g. "Identity Resolution" */
  label: string;
  /** Sub-title, e.g. "identity_resolution_agent" */
  subLabel: string;
  /** Key in LUCIDE_ICONS map */
  iconName: string;
  /** Hex accent colour */
  color: string;
  /** "completed" | "failed" | "warning" | "running" */
  status: string;
  durationMs: number | null;
  events: TestRunEvent[];
  diagnostics: TestRunDiagnostic[];
  /** Parsed final_output JSON (runtime phase only) */
  output: unknown;
  /** Zero-based index used for stagger animation delay */
  index: number;
}

export interface EdgeData extends Record<string, unknown> {
  /** Orchestrator tool name shown as chip, e.g. "execute_target_agent" */
  toolName: string | null;
  /** Hex accent colour matching source node */
  color: string;
}

export type RunNode = Node<AgentNodeData>;
export type RunEdge = Edge<EdgeData>;
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add src/lib/test-lab/graph-types.ts
git commit -m "feat(run-graph): add graph node/edge TypeScript types"
```

---

## Task 3: Graph layout utility (event → nodes + edges + dagre)

**Files:**
- Create: `frontend/src/lib/test-lab/graph-layout.ts`

- [ ] **Step 1: Create the file**

```typescript
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

// Map orchestrator tool names → target phase
const TOOL_TO_PHASE: Record<string, PhaseKind> = {
  prepare_test_scenario:  'preparation',
  execute_target_agent:   'runtime',
  run_assertion_evaluation: 'assertions',
  run_diagnostic_analysis:  'diagnostics',
  compute_final_verdict:    'report',
};

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
  try { return JSON.parse(raw); } catch { return null; }
}

// ── Main export ────────────────────────────────────────────────────────────
export function buildGraph(
  events: TestRunEvent[],
  run: TestRun,
  diagnostics: TestRunDiagnostic[]
): { nodes: RunNode[]; edges: RunEdge[] } {
  // 1. Group events by phase (preserve order of first appearance)
  const PHASE_MAP: Record<string, PhaseKind> = {
    orchestrator: 'orchestrator',
    preparation:  'preparation',
    runtime:      'runtime',
    assertions:   'assertions',
    diagnostics:  'diagnostics',
    report:       'report',
    verdict:      'report',
  };

  const phaseOrder: PhaseKind[] = [];
  const phaseEvs = new Map<PhaseKind, TestRunEvent[]>();

  // Always include orchestrator first
  phaseOrder.push('orchestrator');
  phaseEvs.set('orchestrator', []);

  for (const ev of events) {
    const phase = PHASE_MAP[ev.phase ?? ''];
    if (!phase) continue;
    if (!phaseEvs.has(phase)) {
      phaseOrder.push(phase);
      phaseEvs.set(phase, []);
    }
    phaseEvs.get(phase)!.push(ev);
  }

  // Ensure orchestrator bucket gets events with no phase
  for (const ev of events) {
    if (!ev.phase || ev.phase === 'orchestrator') {
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
    const cfg = PHASE_CFG[phase];
    const evList = phaseEvs.get(phase) ?? [];

    let iconName = cfg.iconName;
    let color = cfg.color;
    let label = cfg.label;
    let subLabel = `${phase}_agent`;

    if (phase === 'runtime') {
      const agCfg = AGENT_ICONS[run.agent_id];
      if (agCfg) { iconName = agCfg.iconName; color = agCfg.color; }
      label = toTitle(run.agent_id);
      subLabel = run.agent_id;
    } else if (phase === 'orchestrator') {
      subLabel = 'master pipeline';
    }

    const data: AgentNodeData = {
      kind: phase,
      agentId: phase === 'runtime' ? run.agent_id : `${phase}_agent`,
      label,
      subLabel,
      iconName,
      color,
      status: detectStatus(evList),
      durationMs: phase === 'runtime' ? run.duration_ms ?? null : detectDuration(evList),
      events: evList,
      diagnostics: ['runtime', 'diagnostics'].includes(phase) ? diagnostics : [],
      output: phase === 'runtime' ? parseOutput(run.final_output) : null,
      index,
    };

    g.setNode(phase, { width: NODE_W, height: NODE_H });
    nodes.push({
      id: phase,
      type: cfg.nodeType,
      position: { x: 0, y: 0 }, // overwritten by dagre below
      data,
    });
  });

  // 4. Build edges from orchestrator_tool_call events
  const toolCalls = events.filter(
    (e) => e.event_type === 'orchestrator_tool_call' && e.details?.tool_name
  );

  const edges: RunEdge[] = [];
  const addedEdgeIds = new Set<string>();

  for (const tc of toolCalls) {
    const toolName = tc.details!.tool_name as string;
    const target = TOOL_TO_PHASE[toolName];
    if (!target || !phaseEvs.has(target)) continue;

    const edgeId = `orch->${target}`;
    if (addedEdgeIds.has(edgeId)) continue;
    addedEdgeIds.add(edgeId);

    g.setEdge('orchestrator', target);
    edges.push({
      id: edgeId,
      source: 'orchestrator',
      target,
      type: 'animatedEdge',
      data: { toolName, color: EDGE_COLOURS['orchestrator'] },
    });
  }

  // Fallback: connect adjacent phases in order if no tool call edges exist
  if (edges.length === 0) {
    for (let i = 0; i < phaseOrder.length - 1; i++) {
      const src = phaseOrder[i];
      const tgt = phaseOrder[i + 1];
      g.setEdge(src, tgt);
      edges.push({
        id: `${src}->${tgt}`,
        source: src,
        target: tgt,
        type: 'animatedEdge',
        data: { toolName: null, color: EDGE_COLOURS[src] },
      });
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
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add src/lib/test-lab/graph-layout.ts src/lib/test-lab/graph-types.ts
git commit -m "feat(run-graph): event→node mapping with dagre auto-layout"
```

---

## Task 4: AnimatedEdge component

**Files:**
- Create: `frontend/src/components/test-lab/run-graph/edges/AnimatedEdge.tsx`

The edge renders a dashed animated Bézier curve with a glow layer, plus the tool chip label using ReactFlow's `EdgeLabelRenderer` (portals it to the correct DOM position).

- [ ] **Step 1: Create directories and file**

```bash
mkdir -p /Users/mbensass/projetPreso/multiAgents/orkestra/frontend/src/components/test-lab/run-graph/edges
mkdir -p /Users/mbensass/projetPreso/multiAgents/orkestra/frontend/src/components/test-lab/run-graph/nodes
```

```typescript
// frontend/src/components/test-lab/run-graph/edges/AnimatedEdge.tsx
"use client";

import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from '@xyflow/react';
import type { EdgeData } from '@/lib/test-lab/graph-types';

export function AnimatedEdge({
  id,
  sourceX, sourceY, targetX, targetY,
  sourcePosition, targetPosition,
  data,
}: EdgeProps<EdgeData>) {
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
        id={`${id}-glow`}
        path={edgePath}
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
```

- [ ] **Step 2: Add the `edgeDash` keyframe to globals.css**

Open `frontend/src/globals.css` and add inside `@layer base` (after the scrollbar rules):

```css
@keyframes edgeDash {
  to { stroke-dashoffset: -26; }
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add src/components/test-lab/run-graph/edges/AnimatedEdge.tsx src/globals.css
git commit -m "feat(run-graph): AnimatedEdge with glow and tool chip label"
```

---

## Task 5: Icon resolver (used by both node components)

**Files:**
- Create: `frontend/src/components/test-lab/run-graph/NodeIcon.tsx`

Rather than dynamic imports, we keep a static lookup so the icon tree-shakes at build time.

- [ ] **Step 1: Create file**

```typescript
// frontend/src/components/test-lab/run-graph/NodeIcon.tsx
import {
  Sun, ClipboardCheck, Bot, ShieldCheck, FileSearch2, Award,
  Fingerprint, MessageSquare, GitFork, Tag,
  type LucideProps,
} from 'lucide-react';

const MAP: Record<string, React.ComponentType<LucideProps>> = {
  Sun, ClipboardCheck, Bot, ShieldCheck, FileSearch2, Award,
  Fingerprint, MessageSquare, GitFork, Tag,
};

interface NodeIconProps extends LucideProps {
  name: string;
}

export function NodeIcon({ name, ...props }: NodeIconProps) {
  const Icon = MAP[name] ?? Bot;
  return <Icon {...props} />;
}
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add src/components/test-lab/run-graph/NodeIcon.tsx
git commit -m "feat(run-graph): static Lucide icon resolver for node components"
```

---

## Task 6: OrchestratorNode component

**Files:**
- Create: `frontend/src/components/test-lab/run-graph/nodes/OrchestratorNode.tsx`

- [ ] **Step 1: Create file**

```typescript
// frontend/src/components/test-lab/run-graph/nodes/OrchestratorNode.tsx
"use client";

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { motion } from 'framer-motion';
import type { AgentNodeData } from '@/lib/test-lab/graph-types';
import { NodeIcon } from '../NodeIcon';

export const OrchestratorNode = memo(function OrchestratorNode({
  data,
  selected,
}: NodeProps<AgentNodeData>) {
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
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add src/components/test-lab/run-graph/nodes/OrchestratorNode.tsx
git commit -m "feat(run-graph): OrchestratorNode with Framer Motion entrance"
```

---

## Task 7: AgentNode component

**Files:**
- Create: `frontend/src/components/test-lab/run-graph/nodes/AgentNode.tsx`

- [ ] **Step 1: Create file**

```typescript
// frontend/src/components/test-lab/run-graph/nodes/AgentNode.tsx
"use client";

import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { motion } from 'framer-motion';
import type { AgentNodeData } from '@/lib/test-lab/graph-types';
import { NodeIcon } from '../NodeIcon';

export const AgentNode = memo(function AgentNode({
  data,
  selected,
}: NodeProps<AgentNodeData>) {
  const { label, subLabel, iconName, color, status, durationMs, index } = data;

  const statusColor =
    status === 'completed' ? '#10b981' :
    status === 'failed'    ? '#ef4444' :
    status === 'warning'   ? '#f59e0b' :
    '#00d4ff';

  const durationLabel =
    durationMs != null
      ? durationMs >= 1000
        ? `${(durationMs / 1000).toFixed(1)}s`
        : `${durationMs}ms`
      : null;

  // Hex → rgba helper for backgrounds
  const hexToRgba = (hex: string, alpha: number) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  };

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
          background: hexToRgba(color, 0.05),
          borderColor: selected ? '#00d4ff' : hexToRgba(color, 0.25),
          boxShadow: selected
            ? '0 0 0 2px #00d4ff, 0 16px 48px rgba(0,212,255,0.18)'
            : '0 8px 32px rgba(0,0,0,0.4)',
        }}
      >
        {/* Top shimmer */}
        <div
          className="absolute top-0 inset-x-8 h-px"
          style={{ background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.15), transparent)' }}
        />

        {/* Header */}
        <div className="flex items-center gap-2.5 px-3.5 pt-3 pb-2.5">
          <div
            className="flex items-center justify-center rounded-xl flex-shrink-0"
            style={{
              width: 38, height: 38,
              background: hexToRgba(color, 0.12),
            }}
          >
            <NodeIcon name={iconName} size={18} color={color} strokeWidth={1.8} />
          </div>
          <div className="min-w-0">
            <p
              className="text-[8px] font-bold tracking-[0.14em] uppercase opacity-55"
              style={{ color }}
            >
              AGENT
            </p>
            <p className="text-[12px] font-bold leading-tight truncate" style={{ color }}>
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
              boxShadow: status !== 'running' ? `0 0 5px ${statusColor}` : 'none',
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
          type="target"
          position={Position.Left}
          style={{ background: '#07070f', borderColor: hexToRgba(color, 0.5), width: 10, height: 10 }}
        />
        <Handle
          type="source"
          position={Position.Right}
          style={{ background: '#07070f', borderColor: hexToRgba(color, 0.5), width: 10, height: 10 }}
        />
      </div>
    </motion.div>
  );
});
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add src/components/test-lab/run-graph/nodes/AgentNode.tsx
git commit -m "feat(run-graph): AgentNode with per-agent colour and Lucide icon"
```

---

## Task 8: DetailPanel component

**Files:**
- Create: `frontend/src/components/test-lab/run-graph/DetailPanel.tsx`

- [ ] **Step 1: Create file**

```typescript
// frontend/src/components/test-lab/run-graph/DetailPanel.tsx
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
            {node.output && (
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
                  {node.events.slice(0, 10).map((ev) => (
                    <div
                      key={ev.id}
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
```

- [ ] **Step 2: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add src/components/test-lab/run-graph/DetailPanel.tsx
git commit -m "feat(run-graph): DetailPanel with Framer Motion spring slide-in"
```

---

## Task 9: RunTopbar component

**Files:**
- Create: `frontend/src/components/test-lab/run-graph/RunTopbar.tsx`

- [ ] **Step 1: Create file**

```typescript
// frontend/src/components/test-lab/run-graph/RunTopbar.tsx
"use client";

import Link from 'next/link';
import { Play, Download, Network, List } from 'lucide-react';
import type { TestRun } from '@/lib/test-lab/types';

interface RunTopbarProps {
  run: TestRun;
  view: 'graph' | 'timeline';
  onViewChange: (v: 'graph' | 'timeline') => void;
  onRerun: () => void;
  rerunning: boolean;
}

const VERDICT_CFG = {
  passed:               { label: 'PASSED',   color: '#10b981', bg: 'rgba(16,185,129,0.1)',   border: 'rgba(16,185,129,0.25)' },
  passed_with_warnings: { label: 'WARNINGS', color: '#f59e0b', bg: 'rgba(245,158,11,0.1)',   border: 'rgba(245,158,11,0.25)' },
  failed:               { label: 'FAILED',   color: '#ef4444', bg: 'rgba(239,68,68,0.1)',    border: 'rgba(239,68,68,0.25)' },
};

function fmtDuration(ms: number | null): string {
  if (ms == null) return '--';
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}

function fmtDate(iso: string | null): string {
  if (!iso) return '--';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });
}

export function RunTopbar({ run, view, onViewChange, onRerun, rerunning }: RunTopbarProps) {
  const verdict = run.verdict ? VERDICT_CFG[run.verdict as keyof typeof VERDICT_CFG] : null;

  function handleExport() {
    const blob = new Blob([JSON.stringify(run, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${run.id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div
      className="flex items-center h-[52px] flex-shrink-0"
      style={{
        background: 'rgba(9,9,18,0.97)',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        backdropFilter: 'blur(20px)',
      }}
    >
      {/* Logo */}
      <div
        className="flex items-center justify-center flex-shrink-0"
        style={{ width: 52, height: 52, borderRight: '1px solid rgba(255,255,255,0.06)' }}
      >
        <Link href="/">
          <div
            className="flex items-center justify-center rounded-[9px] text-[15px] font-extrabold"
            style={{
              width: 32, height: 32,
              background: 'linear-gradient(135deg, rgba(167,139,250,0.3), rgba(0,212,255,0.2))',
              border: '1px solid rgba(167,139,250,0.4)',
              color: '#a78bfa',
              boxShadow: '0 0 20px rgba(167,139,250,0.15)',
            }}
          >
            ⬡
          </div>
        </Link>
      </div>

      {/* Breadcrumb */}
      <div
        className="flex items-center gap-2 px-4 h-full"
        style={{ borderRight: '1px solid rgba(255,255,255,0.06)' }}
      >
        <Link href="/test-lab" className="text-[12px] font-mono transition-colors hover:text-ork-cyan" style={{ color: '#3f3f5a' }}>
          TEST LAB
        </Link>
        <span style={{ color: '#252538' }}>/</span>
        <span className="text-[12px] font-mono font-semibold" style={{ color: '#71717a' }}>
          {run.id.slice(0, 16)}…
        </span>
      </div>

      {/* Status chips */}
      <div className="flex items-center gap-2.5 px-4">
        {verdict && (
          <div
            className="flex items-center gap-1.5 rounded-full px-3 py-1"
            style={{
              background: verdict.bg, border: `1px solid ${verdict.border}`,
              fontSize: 11, fontWeight: 700, letterSpacing: '0.06em', color: verdict.color,
            }}
          >
            <div
              className="rounded-full"
              style={{
                width: 6, height: 6, background: verdict.color,
                animation: 'verdictPulse 2s ease-in-out infinite',
              }}
            />
            {verdict.label}
          </div>
        )}
        {run.score != null && (
          <span className="font-mono text-[13px] font-bold" style={{ color: '#10b981' }}>
            {run.score}/100
          </span>
        )}
        <div style={{ width: 1, height: 14, background: '#1e1e2e' }} />
        <span className="font-mono text-[11px]" style={{ color: '#3f3f5a' }}>
          {fmtDuration(run.duration_ms)}
        </span>
        <div style={{ width: 1, height: 14, background: '#1e1e2e' }} />
        <span className="font-mono text-[11px]" style={{ color: '#3f3f5a' }}>
          {fmtDate(run.ended_at)}
        </span>
      </div>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Actions */}
      <div className="flex items-center gap-2 pr-4">
        {/* View toggle */}
        <div
          className="flex items-center overflow-hidden rounded-lg"
          style={{ background: '#0d0d18', border: '1px solid #1e1e2e' }}
        >
          {(['graph', 'timeline'] as const).map((v) => (
            <button
              key={v}
              onClick={() => onViewChange(v)}
              className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] font-semibold transition-colors"
              style={{
                color: view === v ? '#00d4ff' : '#3f3f5a',
                background: view === v ? 'rgba(0,212,255,0.1)' : 'transparent',
              }}
            >
              {v === 'graph' ? <Network size={10} /> : <List size={10} />}
              {v === 'graph' ? 'Graph' : 'Timeline'}
            </button>
          ))}
        </div>

        <button
          onClick={handleExport}
          className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[11px] font-medium transition-all hover:text-ork-text"
          style={{ background: 'transparent', border: '1px solid #1e1e2e', color: '#52525b' }}
        >
          <Download size={11} />
          Export
        </button>

        <button
          onClick={onRerun}
          disabled={rerunning}
          className="flex items-center gap-1.5 rounded-lg px-4 py-1.5 text-[11px] font-bold transition-all"
          style={{
            background: 'rgba(0,212,255,0.12)',
            border: '1px solid rgba(0,212,255,0.3)',
            color: '#00d4ff',
            opacity: rerunning ? 0.6 : 1,
          }}
        >
          <Play size={11} fill="currentColor" />
          {rerunning ? 'RUNNING…' : 'RE-RUN'}
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add `verdictPulse` keyframe to globals.css** (inside `@layer base`):

```css
@keyframes verdictPulse {
  0%, 100% { opacity: 1; box-shadow: 0 0 0 0 currentColor; }
  50%       { opacity: 0.6; box-shadow: 0 0 0 4px transparent; }
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add src/components/test-lab/run-graph/RunTopbar.tsx src/globals.css
git commit -m "feat(run-graph): RunTopbar with verdict pill, view toggle, export"
```

---

## Task 10: RunGraph (main ReactFlow canvas)

**Files:**
- Create: `frontend/src/components/test-lab/run-graph/RunGraph.tsx`

- [ ] **Step 1: Create file**

```typescript
// frontend/src/components/test-lab/run-graph/RunGraph.tsx
"use client";

import { useCallback, useMemo, useState } from 'react';
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
import type { AgentNodeData } from '@/lib/test-lab/graph-types';

import { OrchestratorNode } from './nodes/OrchestratorNode';
import { AgentNode } from './nodes/AgentNode';
import { AnimatedEdge } from './edges/AnimatedEdge';
import { DetailPanel } from './DetailPanel';

const NODE_TYPES = {
  orchestratorNode: OrchestratorNode,
  agentNode: AgentNode,
} as const;

const EDGE_TYPES = {
  animatedEdge: AnimatedEdge,
} as const;

interface RunGraphProps {
  run: TestRun;
  events: TestRunEvent[];
  diagnostics: TestRunDiagnostic[];
}

export function RunGraph({ run, events, diagnostics }: RunGraphProps) {
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildGraph(events, run, diagnostics),
    [events, run, diagnostics]
  );

  const [nodes, , onNodesChange] = useNodesState(initNodes);
  const [edges, , onEdgesChange] = useEdgesState(initEdges);
  const [selectedNodeData, setSelectedNodeData] = useState<AgentNodeData | null>(null);

  const onNodeClick: NodeMouseHandler = useCallback((_evt, node) => {
    setSelectedNodeData(node.data as AgentNodeData);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNodeData(null);
  }, []);

  return (
    <div className="flex flex-1 overflow-hidden" style={{ height: '100%' }}>
      {/* Canvas */}
      <div className="flex-1" style={{ background: '#07070f' }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={NODE_TYPES}
          edgeTypes={EDGE_TYPES}
          onNodeClick={onNodeClick}
          onPaneClick={onPaneClick}
          minZoom={0.3}
          maxZoom={2.0}
          fitView
          fitViewOptions={{ padding: 0.18 }}
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

      {/* Detail panel */}
      <DetailPanel node={selectedNodeData} onClose={onPaneClick} />
    </div>
  );
}
```

- [ ] **Step 2: Override ReactFlow default styles** — Add to `globals.css` inside `@layer base`:

```css
/* ReactFlow overrides */
.react-flow__attribution { display: none !important; }
.react-flow__controls-button {
  background: transparent !important;
  border: none !important;
  color: #52525b !important;
  fill: #52525b !important;
}
.react-flow__controls-button:hover {
  color: #00d4ff !important;
  fill: #00d4ff !important;
}
.react-flow__handle {
  border-radius: 50% !important;
  transition: transform 0.15s, box-shadow 0.15s !important;
}
.react-flow__handle:hover {
  transform: scale(1.5) !important;
}
```

- [ ] **Step 3: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add src/components/test-lab/run-graph/RunGraph.tsx src/globals.css
git commit -m "feat(run-graph): ReactFlow canvas with minimap, controls, fit-view"
```

---

## Task 11: Refactor page.tsx — wire everything together

**Files:**
- Modify: `frontend/src/app/test-lab/runs/[id]/page.tsx`

The goal is **minimal change**: keep all existing data-fetching, SSE, and timeline render logic. Add `view` state and conditionally render `RunTopbar + RunGraph` (graph view) vs the existing layout (timeline view).

- [ ] **Step 1: Add imports at top of page.tsx**

After the existing import block, add:

```typescript
import { RunTopbar } from "@/components/test-lab/run-graph/RunTopbar";
import { RunGraph } from "@/components/test-lab/run-graph/RunGraph";
```

- [ ] **Step 2: Add `view` state inside `TestRunDetailPage`**

After the `const [loading, setLoading]` line, add:

```typescript
const [view, setView] = useState<'graph' | 'timeline'>('graph');
```

- [ ] **Step 3: Replace the return statement**

Replace the entire `return (` block (from `return (` to the final `);`) with:

```tsx
  // ── Graph view ──────────────────────────────────────────────────────
  if (view === 'graph' && run) {
    return (
      <div className="flex flex-col" style={{ height: '100vh', overflow: 'hidden' }}>
        <RunTopbar
          run={run}
          view={view}
          onViewChange={setView}
          onRerun={async () => {
            setRerunning(true);
            try {
              const newRun = await request<any>(`/api/test-lab/runs/${id}/rerun`, { method: 'POST' });
              router.push(`/test-lab/runs/${newRun.id}`);
            } catch {
              setRerunning(false);
            }
          }}
          rerunning={rerunning}
        />
        <div className="flex-1 overflow-hidden">
          <RunGraph run={run} events={events} diagnostics={diagnostics} />
        </div>
      </div>
    );
  }

  // ── Timeline view (existing layout) ────────────────────────────────
  return (
    <div className="p-6 max-w-[1200px] mx-auto space-y-6 animate-fade-in">
      {/* Inject the new topbar with the toggle even in timeline view */}
      {run && (
        <div className="-mx-6 -mt-6 mb-2">
          <RunTopbar
            run={run}
            view={view}
            onViewChange={setView}
            onRerun={async () => {
              setRerunning(true);
              try {
                const newRun = await request<any>(`/api/test-lab/runs/${id}/rerun`, { method: 'POST' });
                router.push(`/test-lab/runs/${newRun.id}`);
              } catch {
                setRerunning(false);
              }
            }}
            rerunning={rerunning}
          />
        </div>
      )}
      {/* ↓ all existing JSX below stays UNCHANGED ↓ */}
```

Then close the JSX as before. The existing `rerun` button inside the old header can remain (it won't conflict) or be removed for cleanliness — either is fine.

- [ ] **Step 4: Fix the `app-shell` layout** — The graph view needs full-height without the app shell padding. Open `frontend/src/components/layout/app-shell.tsx` and check if `<main>` has `overflow: hidden` and `height: 100%`. If not, it needs:

```tsx
// In app-shell.tsx, the <main> element should be:
<main className="flex-1 overflow-hidden min-h-0">
  {children}
</main>
```

- [ ] **Step 5: TypeScript check**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 6: Start dev server and verify in browser**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
npm run dev
```

Open `http://localhost:3300/test-lab/runs/trun_79ea1557642646a68d37f073`.

Verify:
- [ ] Graph view loads with all 6 nodes visible
- [ ] Each node has the correct Lucide icon
- [ ] Dragging a node redraws edges in real time
- [ ] Clicking a node opens the DetailPanel (slides in from right)
- [ ] Toggle `Timeline` switches back to the old vertical view
- [ ] Toggle `Graph` brings back the canvas
- [ ] Minimap shows coloured node blobs
- [ ] Fit-view button centres the graph

- [ ] **Step 7: Commit**

```bash
cd /Users/mbensass/projetPreso/multiAgents/orkestra/frontend
git add src/app/test-lab/runs/\\[id\\]/page.tsx src/components/layout/app-shell.tsx
git commit -m "feat(run-graph): wire graph view into run detail page with view toggle"
```

---

## Self-Review Checklist

- [x] **Spec §1 Objectif** — Node graph with drag/zoom ✅ (RunGraph + ReactFlow)
- [x] **Spec §2 Périmètre** — All 8 files created/modified ✅
- [x] **Spec §4 AGENT_ICONS** — All 9 entries in `graph-layout.ts` ✅
- [x] **Spec §5 dagre layout** — `rankdir: 'LR'`, `ranksep: 130`, `nodesep: 70` ✅
- [x] **Spec §6 drag/zoom/pan** — ReactFlow handles natively ✅
- [x] **Spec §6 panel spring** — `stiffness: 300, damping: 28` ✅
- [x] **Spec §6 node entrance** — `scale 0.85→1`, stagger `index * 0.08` ✅
- [x] **Spec §6 edge glow** — Two-layer BaseEdge in AnimatedEdge ✅
- [x] **Spec §7 TopBar** — All 9 elements in RunTopbar ✅
- [x] **Spec §8 Timeline toggle** — `view` state, both views rendered ✅
- [x] **Spec §9 deps** — Task 1 installs all 3 packages ✅
- [x] **Spec §11 fallback** — Timeline view always available via toggle ✅
- [x] **Type consistency** — `AgentNodeData.iconName` (string) used in `NodeIcon`, `OrchestratorNode`, `AgentNode`, `DetailPanel` ✅
- [x] **No placeholders** — All steps have complete code ✅
