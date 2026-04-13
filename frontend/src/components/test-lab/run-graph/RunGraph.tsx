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

export function RunGraph({ run, events, diagnostics }: RunGraphProps) {
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildGraph(events, run, diagnostics),
    [events, run, diagnostics]
  );

  const [nodes, , onNodesChange] = useNodesState<RunNode>(initNodes);
  const [edges, , onEdgesChange] = useEdgesState<RunEdge>(initEdges);
  const [selectedNodeData, setSelectedNodeData] = useState<AgentNodeData | null>(null);

  const onNodeClick: NodeMouseHandler = useCallback((_evt, node) => {
    setSelectedNodeData(node.data as AgentNodeData);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNodeData(null);
  }, []);

  // onInit fires after ReactFlow is mounted and the store is ready.
  // We use requestAnimationFrame to defer until the browser has painted
  // all node DOM elements so measurements are accurate.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const onInit = useCallback((instance: any) => {
    window.requestAnimationFrame(() => {
      instance.fitView({ padding: 0.18, maxZoom: 1.4, duration: 0 });
    });
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
