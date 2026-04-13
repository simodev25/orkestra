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
  label: string;
  subLabel: string;
  iconName: string;
  color: string;
  /** "completed" | "failed" | "warning" | "running" */
  status: string;
  /** Whether the node is currently revealed (progressive animation) */
  visible: boolean;
  durationMs: number | null;
  events: TestRunEvent[];
  diagnostics: TestRunDiagnostic[];
  output: unknown;
  index: number;
}

export interface EdgeData extends Record<string, unknown> {
  toolName: string | null;
  color: string;
  /** Edge is visible (target node revealed) */
  visible?: boolean;
  /** Edge is actively transmitting (tool call fired, target not yet started) */
  active?: boolean;
}

export type RunNode = Node<AgentNodeData>;
export type RunEdge = Edge<EdgeData>;
